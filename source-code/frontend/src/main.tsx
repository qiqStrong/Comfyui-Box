import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'
import './styles/main.css'
import './i18n'
import { router } from './router'
import { ThemeProvider } from './contexts/ThemeContext'
import { NavigationGuardProvider } from './contexts/NavigationGuardContext'
import { EnvSwitchGuardProvider } from './contexts/EnvSwitchGuardContext'
import { useModuleConfigStore } from './stores/useModuleConfigStore'
import { useSettingsStore } from './stores/useSettingsStore'
import { useEnvStore } from './stores/useEnvStore'
import { useGlobalTextSelectionStore } from './stores/useGlobalTextSelectionStore'
import { usePluginBadgeInit } from './hooks/usePluginBadgeInit'
import { useAutoUpdateCheck } from './hooks/useAutoUpdateCheck'
import { useAppVersion } from './hooks/useAppVersion'
import { useChangelogStore } from './stores/useChangelogStore'
import { useWarningStore } from './stores/useWarningStore'
import { ChangelogDialog } from './components/about/ChangelogDialog'
import { fetchReleases } from './api/githubApi'
import { GlobalTextSelectionButton } from './components/common/GlobalTextSelectionButton'
import { SystemProxyDetectedDialog } from './components/common/SystemProxyDetectedDialog'
import { OnboardingDialog } from './components/common/OnboardingDialog'
import { waitForAPI, validateAPIMethods, REQUIRED_API_METHODS, isDevelopment } from './utils/pywebview'
import { loadLoggerConfigFromSettings } from './utils/logger'
import { Button } from '@/components/ui/Button'

// 全局日志缓存
interface LogEntry {
  id: string
  timestamp: string
  level: 'INFO' | 'WARNING' | 'ERROR' | 'DEBUG'
  source: 'comfyui' | 'system'
  message: string
  isUpdate?: boolean
}

const MAX_LOG_CACHE = 1000
const logCache: LogEntry[] = []

function handleComfyUILog(log: LogEntry): void {
  if (!(window as any).__COMFY_NEXUS__) {
    (window as any).__COMFY_NEXUS__ = {}
  }
  const namespace = (window as any).__COMFY_NEXUS__
  
  namespace.logsCleared = false
  
  if (log.isUpdate) {
    const index = logCache.findIndex(item => item.id === log.id)
    if (index !== -1) {
      logCache[index] = { ...logCache[index], message: log.message, timestamp: log.timestamp }
    }
  } else {
    logCache.push(log)
    if (logCache.length > MAX_LOG_CACHE) {
      logCache.shift()
    }
  }
  
  window.dispatchEvent(new CustomEvent('comfyui:log-received', { detail: log }))
}

;(window as any).onComfyUILog = handleComfyUILog

;(window as any).refreshComfyUIStatus = async (isStarting?: boolean) => {
  console.log('[main.tsx] 收到后端通知，刷新 ComfyUI 状态, isStarting:', isStarting)
  const { useProcessStore } = await import('./stores/useProcessStore')
  const store = useProcessStore.getState()
  
  if (isStarting !== undefined) {
    store.setStarting(isStarting)
  }
  
  store.loadComfyUIStatus()
}

if (!(window as any).__COMFY_NEXUS__) {
  (window as any).__COMFY_NEXUS__ = {}
}
;(window as any).__COMFY_NEXUS__.logCache = {
  getLogs: (): LogEntry[] => [...logCache],
  clear: (): void => { logCache.length = 0 }
}

window.addEventListener('comfyui:clear-logs', () => {
  console.log('[main.tsx] 收到清屏事件，清空全局日志缓存')
  logCache.length = 0
  if (!(window as any).__COMFY_NEXUS__) {
    (window as any).__COMFY_NEXUS__ = {}
  }
  const namespace = (window as any).__COMFY_NEXUS__
  namespace.logsCleared = true
  namespace.skipHistoryLogs = true
})

// 开发环境调试工具
if (isDevelopment()) {
  (window as any).__DEBUG__ = {
    getAPIState: () => ({
      isDevelopment: isDevelopment(),
      pywebviewExists: !!window.pywebview,
      apiExists: !!(window.pywebview?.api),
      availableMethods: window.pywebview?.api 
        ? Object.keys(window.pywebview.api).filter(key => typeof (window.pywebview.api as any)[key] === 'function')
        : []
    }),
    forceReload: () => window.location.reload(),
    clearCache: () => {
      localStorage.clear()
      sessionStorage.clear()
      console.log('[DEBUG] 缓存已清除')
    },
    validateAPI: () => validateAPIMethods(REQUIRED_API_METHODS),
    testAPICall: async (methodName: string, ...args: any[]) => {
      if (!window.pywebview?.api) {
        console.error('[DEBUG] API 不可用')
        return
      }
      try {
        const result = await (window.pywebview.api as any)[methodName](...args)
        console.log('[DEBUG] API 调用成功:', result)
        return result
      } catch (error) {
        console.error('[DEBUG] API 调用失败:', error)
        throw error
      }
    }
  }
  console.log('[DEBUG] 调试工具已加载，使用 window.__DEBUG__ 访问')
}

// 应用初始化组件
function AppInitializer() {
  const [isReady, setIsReady] = useState(false)
  const [isPywebviewReady, setIsPywebviewReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showChangelog, setShowChangelog] = useState(false)
  const loadConfig = useModuleConfigStore((state) => state.loadConfig)
  const loadSystemSettings = useSettingsStore((state) => state.loadSystemSettings)
  const fetchEnvironments = useEnvStore((state) => state.fetchEnvironments)
  const loading = useModuleConfigStore((state) => state.loading)
  const globalTextSelection = useSettingsStore((state) => state.systemSettings.globalTextSelection)
  const isGlobalTextSelectionModeActive = useGlobalTextSelectionStore((state) => state.active)
  const setGlobalTextSelectionVisible = useGlobalTextSelectionStore((state) => state.setVisible)
  
  const { version: currentVersion, loading: versionLoading } = useAppVersion({ enabled: isPywebviewReady })
  const { shouldShowChangelog, setLastViewedVersion } = useChangelogStore()
  const { warnings, setWarningDismissed, loadWarnings } = useWarningStore()
  
  // 系统代理检测弹窗状态
  const [showSystemProxyDialog, setShowSystemProxyDialog] = useState(false)
  const [systemProxyInfo, setSystemProxyInfo] = useState({ host: '', port: '' })
  
  // 初始化插件徽章
  usePluginBadgeInit()
  
  // 自动检查应用更新
  useAutoUpdateCheck()
  
  // 阶段 1: 等待 pywebview API 就绪
  useEffect(() => {
    const initializeAPI = async () => {
      console.log('[AppInitializer] 开始初始化...')
      
      try {
        // 等待 API 就绪
        const apiReady = await waitForAPI(5000)
        
        if (!apiReady && !isDevelopment()) {
          console.error('[AppInitializer] API 初始化超时')
          setError('应用初始化失败：API 未就绪')
          return
        }
        
        // 验证必需的 API 方法
        if (!isDevelopment()) {
          const validation = validateAPIMethods(REQUIRED_API_METHODS)
          if (!validation.valid) {
            console.error('[AppInitializer] API 方法验证失败，缺失方法:', validation.missing)
            // 不阻止启动，但记录警告
            console.warn('[AppInitializer] 应用将继续启动，但某些功能可能不可用')
          }
        }
        
        console.log('[AppInitializer] API 就绪检测完成')
        setIsPywebviewReady(true)
        
        // 立即发送心跳信号，通知后端前端已就绪
        try {
          await window.pywebview?.api?.ping()
          console.log('[AppInitializer] 心跳信号已发送')
        } catch (e) {
          console.warn('[AppInitializer] 心跳信号发送失败:', e)
        }
      } catch (err) {
        console.error('[AppInitializer] API 初始化异常:', err)
        setError('应用初始化失败')
      }
    }
    
    initializeAPI()
  }, [])
  
  useEffect(() => {
    if (isReady && !versionLoading && currentVersion) {
      if (!shouldShowChangelog(currentVersion)) return

      // 自动弹出前先确认确有内容：日志为空时不弹窗，但写入已读版本避免反复判定
      let cancelled = false
      fetchReleases()
        .then((releases) => {
          if (cancelled) return
          if (!releases || releases.length === 0) {
            console.log('[AppInitializer] 更新日志为空，跳过自动弹窗')
            setLastViewedVersion(currentVersion)
            return
          }
          console.log('[AppInitializer] 检测到需要显示更新日志弹窗')
          setShowChangelog(true)
        })
        .catch(() => {
          if (!cancelled) setLastViewedVersion(currentVersion)
        })

      return () => {
        cancelled = true
      }
    }
  }, [isReady, versionLoading, currentVersion, shouldShowChangelog, setLastViewedVersion])
  
  const handleChangelogClose = () => {
    setShowChangelog(false)
  }
  
  const handleVersionRecorded = (version: string) => {
    setLastViewedVersion(version)
  }
  
  // 阶段 2: 当 pywebview 准备好后，加载配置
  useEffect(() => {
    if (isPywebviewReady && !isReady && !error) {
      console.log('[AppInitializer] 开始加载配置...')
      
      // 加载日志配置
      loadLoggerConfigFromSettings()
        .then(() => {
          console.log('[AppInitializer] 日志配置加载完成')
        })
        .catch((err) => {
          console.warn('[AppInitializer] 日志配置加载失败，使用默认配置:', err)
        })
      
      // 并行加载模块配置和系统设置
      Promise.all([
        loadConfig().then(() => {
          console.log('[AppInitializer] 模块配置加载完成')
        }),
        loadSystemSettings().then(() => {
          console.log('[AppInitializer] 系统设置加载完成')
        }),
        fetchEnvironments().then(() => {
          console.log('[AppInitializer] 环境列表加载完成')
        }),
        loadWarnings().then(() => {
          console.log('[AppInitializer] 警告设置加载完成')
        })
      ])
        .then(() => {
          console.log('[AppInitializer] 所有配置加载完成')
          setIsReady(true)
        })
        .catch((err) => {
          console.error('[AppInitializer] 加载配置失败:', err)
          // 即使失败也标记为 ready，使用默认配置
          console.warn('[AppInitializer] 使用默认配置继续启动')
          setIsReady(true)
        })
    }
  }, [isPywebviewReady, isReady, error, loadConfig, loadSystemSettings, fetchEnvironments, loadWarnings])
  
  // 阶段 2.5: 检测系统代理
  useEffect(() => {
    if (!isReady) return
    
    const checkSystemProxy = async () => {
      // 检查是否应该显示此提示
      if (!warnings.systemProxyDetected) {
        console.log('[AppInitializer] 系统代理检测提示已关闭')
        // 警告配置是异步加载的，可能在弹窗已打开后才读回"已关闭"，这里一并收起
        setShowSystemProxyDialog(false)
        return
      }
      
      // 获取当前代理设置
      const settingsResult = await window.pywebview?.api?.get_settings()
      if (!settingsResult?.success || !settingsResult?.settings) {
        return
      }
      
      const proxyEnabled = settingsResult.settings.proxy?.enabled === true
      console.log('[AppInitializer] 当前代理设置:', { proxyEnabled })
      
      // 如果代理已启用，不需要提示
      if (proxyEnabled) {
        console.log('[AppInitializer] 代理已启用，跳过检测')
        return
      }
      
      // 检测系统代理
      const systemProxyResult = await window.pywebview?.api?.get_system_proxy()
      console.log('[AppInitializer] 系统代理检测结果:', systemProxyResult)
      
      if (systemProxyResult?.success && systemProxyResult?.enabled && systemProxyResult?.host) {
        console.log('[AppInitializer] 检测到系统代理，显示提示弹窗')
        setSystemProxyInfo({
          host: systemProxyResult.host,
          port: systemProxyResult.port || '80'
        })
        setShowSystemProxyDialog(true)
      }
    }
    
    checkSystemProxy()
  }, [isReady, warnings.systemProxyDetected])
  
  // 处理系统代理检测弹窗确认
  const handleSystemProxyConfirm = async (dontShowAgain: boolean) => {
    // 更新代理设置
    await window.pywebview?.api?.update_settings({
      proxy: {
        enabled: true,
        host: systemProxyInfo.host,
        port: systemProxyInfo.port
      }
    })
    
    // 如果选择了不再显示
    if (dontShowAgain) {
      await setWarningDismissed('systemProxyDetected', true)
    }
  }
  
  useEffect(() => {
    setGlobalTextSelectionVisible(globalTextSelection || false)
  }, [globalTextSelection, setGlobalTextSelectionVisible])
  
  useEffect(() => {
    if (isGlobalTextSelectionModeActive) {
      document.body.classList.add('global-text-selectable')
    } else {
      document.body.classList.remove('global-text-selectable')
    }
    
    return () => {
      document.body.classList.remove('global-text-selectable')
    }
  }, [isGlobalTextSelectionModeActive])
  
  // 错误状态
  if (error) {
    return (
      <div className="dark:bg-dark-primary flex h-screen items-center justify-center bg-background">
        <div className="max-w-md px-4 text-center">
          <div className="text-red-500 mb-4">
            <svg className="mx-auto size-16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="dark:text-dark-foreground mb-2 text-xl font-semibold text-foreground">
            初始化失败
          </h2>
          <p className="mb-4 text-muted-foreground">{error}</p>
          <Button
            onClick={() => window.location.reload()}
          >
            重试
          </Button>
        </div>
      </div>
    )
  }
  
  // 加载状态
  if (!isReady || loading) {
    return (
      <div className="dark:bg-dark-primary flex h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="mx-auto mb-4 size-12 animate-spin rounded-full border-b-2 border-primary"></div>
          <p className="text-muted-foreground">
            {!isPywebviewReady ? '初始化应用...' : '加载配置中...'}
          </p>
        </div>
      </div>
    )
  }
  
  // 阶段 3: 渲染应用
  return (
    <>
      <RouterProvider router={router} />
      <ChangelogDialog
        open={showChangelog}
        onClose={handleChangelogClose}
        currentVersion={currentVersion}
        onVersionRecorded={handleVersionRecorded}
      />
      <SystemProxyDetectedDialog
        open={showSystemProxyDialog}
        onClose={() => setShowSystemProxyDialog(false)}
        systemProxy={systemProxyInfo}
        onConfirm={handleSystemProxyConfirm}
        onDontShowAgain={() => setWarningDismissed('systemProxyDetected', true)}
      />
      <GlobalTextSelectionButton />
      <OnboardingDialog />
    </>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <EnvSwitchGuardProvider>
        <NavigationGuardProvider>
          <AppInitializer />
          <Toaster position="top-center" richColors closeButton duration={1500} style={{ top: '60px' }} />
        </NavigationGuardProvider>
      </EnvSwitchGuardProvider>
    </ThemeProvider>
  </StrictMode>,
)
