/* eslint-disable no-restricted-syntax */
/**
 * 插件市场端到端测试
 * 
 * 测试完整的用户流程：
 * - 完整的插件浏览流程
 * - 完整的插件安装流程
 * - 搜索和过滤功能
 * - 缓存机制
 * - 错误场景处理
 * 
 * 这是一个可选的测试任务，重点验证核心用户场景
 */

import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PluginMarketplace } from '../PluginMarketplace'
import { pluginMarketplaceService } from '@/services/pluginMarketplaceService'
import { Plugin, InstallStage, InstallStatus } from '@/types/plugin-marketplace'

// Mock 插件市场服务
vi.mock('@/services/pluginMarketplaceService', () => ({
  pluginMarketplaceService: {
    getPlugins: vi.fn(),
    getRecommendedPlugins: vi.fn(),
    refreshPlugins: vi.fn(),
    installPlugin: vi.fn(),
    checkDependencies: vi.fn(),
    getInstallProgress: vi.fn()
  }
}))

// Mock UI 组件
vi.mock('@/components/ui/tabs', () => ({
  Tabs: ({ children, value, onValueChange }: any) => (
    <div data-testid="tabs" data-value={value}>
      <div onClick={() => onValueChange?.('library')} data-testid="tab-trigger-library">插件库</div>
      <div onClick={() => onValueChange?.('recommended')} data-testid="tab-trigger-recommended">新手推荐</div>
      <div data-testid={`tab-content-${value}`}>
        {children}
      </div>
    </div>
  ),
  TabsList: ({ children }: any) => <div data-testid="tabs-list">{children}</div>,
  TabsTrigger: ({ children, value }: any) => (
    <button data-testid={`tab-trigger-${value}`}>{children}</button>
  ),
  TabsContent: ({ children, value }: any) => (
    <div data-testid={`tab-content-${value}`}>{children}</div>
  )
}))

vi.mock('@/components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, disabled }: any) => (
    <input
      type="checkbox"
      role="switch"
      checked={checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
      disabled={disabled}
      data-testid="auto-install-switch"
    />
  )
}))

vi.mock('@/components/ui/label', () => ({
  Label: ({ children, htmlFor, className }: any) => (
    <label htmlFor={htmlFor} className={className}>
      {children}
    </label>
  )
}))

vi.mock('@/components/ui/Button', () => ({
  Button: ({ children, onClick, disabled, variant, className }: any) => (
    <button
      onClick={onClick}
      disabled={disabled}
      data-variant={variant}
      className={className}
      data-testid="button"
    >
      {children}
    </button>
  )
}))

vi.mock('@/components/ui/alert', () => ({
  Alert: ({ children, variant }: any) => (
    <div data-testid="alert" data-variant={variant}>
      {children}
    </div>
  ),
  AlertDescription: ({ children }: any) => <div>{children}</div>
}))

// Mock lucide-react 图标；保留真实导出，仅覆盖带 data-testid 断言的图标，
// 避免组件迭代时逐个补齐 mock（未覆盖图标仍为可渲染的 forwardRef 对象）
vi.mock('lucide-react', async (importOriginal) => {
  const actual = await importOriginal<Record<string, any>>()
  return {
    ...actual,
    RefreshCw: () => <span data-testid="refresh-icon">RefreshCw</span>,
    Loader2: () => <span data-testid="loader-icon">Loader2</span>,
    CheckCircle2: () => <span data-testid="check-icon">CheckCircle2</span>,
    XCircle: () => <span data-testid="x-icon">XCircle</span>,
    AlertCircle: () => <span data-testid="alert-icon">AlertCircle</span>,
    Info: () => <span data-testid="info-icon">Info</span>,
    Search: () => <span data-testid="search-icon">Search</span>,
    Download: () => <span data-testid="download-icon">Download</span>,
    ShoppingCart: () => <span data-testid="shopping-cart-icon">ShoppingCart</span>,
    ArrowUpDown: () => <span data-testid="arrow-up-down-icon">ArrowUpDown</span>
  }
})

// 创建测试用的插件数据
const createMockPlugin = (index: number, isInstalled = false): Plugin => ({
  name: `Plugin-${index}`,
  description: `这是插件 ${index} 的描述`,
  repository: `https://github.com/test/plugin-${index}`,
  version_tag: `v1.${index}.0`,
  updated_at: '2024-01-15T10:30:45Z',
  node_count: index * 5,
  is_installed: isInstalled,
  author: `Author-${index}`,
  stars: index * 100,
  downloads: index * 1000,
  tags: ['test', 'plugin']
})

const createMockPlugins = (count: number): Plugin[] => {
  return Array.from({ length: count }, (_, i) => createMockPlugin(i + 1))
}

// 特殊的测试插件
const comfyUIManager: Plugin = {
  name: 'ComfyUI-Manager',
  description: 'ComfyUI 插件管理器',
  repository: 'https://github.com/ltdrdata/ComfyUI-Manager',
  version_tag: 'v1.0.0',
  updated_at: '2024-01-15T10:30:45Z',
  node_count: 10,
  is_installed: false,
  author: 'ltdrdata',
  stars: 1000,
  downloads: 5000,
  tags: ['manager', 'utility']
}

const impactPack: Plugin = {
  name: 'ComfyUI-Impact-Pack',
  description: '强大的图像处理工具包',
  repository: 'https://github.com/ltdrdata/ComfyUI-Impact-Pack',
  version_tag: 'v2.0.0',
  updated_at: '2024-01-20T14:20:00Z',
  node_count: 25,
  is_installed: true,
  author: 'ltdrdata',
  stars: 800,
  downloads: 3000,
  tags: ['image', 'processing']
}

describe('插件市场端到端测试', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    // 设置默认的 mock 返回值
    vi.mocked(pluginMarketplaceService.getPlugins).mockResolvedValue({
      success: true,
      plugins: [comfyUIManager, impactPack, ...createMockPlugins(10)]
    })
    
    vi.mocked(pluginMarketplaceService.getRecommendedPlugins).mockResolvedValue({
      success: true,
      plugins: [comfyUIManager, impactPack]
    })
    
    vi.mocked(pluginMarketplaceService.refreshPlugins).mockResolvedValue({
      success: true,
      message: '刷新成功'
    })
    
    vi.mocked(pluginMarketplaceService.checkDependencies).mockResolvedValue({
      success: true,
      has_conflicts: false,
      conflicts: []
    })
    
    vi.mocked(pluginMarketplaceService.installPlugin).mockResolvedValue({
      success: true,
      task_id: 'task-123',
      message: '安装任务已启动'
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  /**
   * E2E 测试 1: 完整的插件浏览流程
   * 
   * 用户场景：
   * 1. 打开插件市场
   * 2. 浏览插件库中的插件列表
   * 3. 查看插件详细信息
   * 4. 切换到新手推荐选项卡
   * 5. 浏览推荐插件
   */
  it('应该支持完整的插件浏览流程', async () => {
    const user = userEvent.setup()
    
    render(<PluginMarketplace />)
    
    // 步骤 1: 验证插件市场已打开
    expect(screen.getByText('插件市场')).toBeInTheDocument()
    expect(screen.getByText('自动安装依赖')).toBeInTheDocument()
    
    // 步骤 2: 验证插件库选项卡默认显示
    expect(screen.getByTestId('tab-content-library')).toBeInTheDocument()
    
    // 等待插件列表加载
    await waitFor(() => {
      expect(pluginMarketplaceService.getPlugins).toHaveBeenCalledWith(true)
    })
    
    // 步骤 3: 验证插件卡片显示
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
      expect(screen.getByText('ComfyUI-Impact-Pack')).toBeInTheDocument()
    })
    
    // 步骤 4: 切换到新手推荐选项卡
    const recommendedTab = screen.getByTestId('tab-trigger-recommended')
    await user.click(recommendedTab)
    
    // 步骤 5: 验证推荐插件加载
    await waitFor(() => {
      expect(pluginMarketplaceService.getRecommendedPlugins).toHaveBeenCalledWith(true)
    })
    
    // 验证推荐插件显示
    await waitFor(() => {
      const recommendedContent = screen.getByTestId('tab-content-recommended')
      expect(within(recommendedContent).getByText('ComfyUI-Manager')).toBeInTheDocument()
    })
  })

  /**
   * E2E 测试 2: 完整的插件安装流程
   * 
   * 用户场景：
   * 1. 浏览插件列表
   * 2. 选择一个插件进行安装
   * 3. 系统检查依赖冲突
   * 4. 开始安装（克隆 -> 检查依赖 -> 安装依赖）
   * 5. 安装成功
   * 6. 插件状态更新为已安装
   */
  it('应该支持完整的插件安装流程', async () => {
    const user = userEvent.setup()
    
    // Mock 安装进度的不同阶段
    let progressCallCount = 0
    vi.mocked(pluginMarketplaceService.getInstallProgress).mockImplementation(() => {
      progressCallCount++
      
      // 第 1-2 次调用：克隆阶段
      if (progressCallCount <= 2) {
        return Promise.resolve({
          success: true,
          task: {
            task_id: 'task-123',
            plugin_name: 'ComfyUI-Manager',
            github_url: 'https://github.com/ltdrdata/ComfyUI-Manager',
            stage: InstallStage.CLONING,
            progress: 30,
            current_package: '',
            status: InstallStatus.RUNNING,
            error_message: '',
            log_path: '',
            started_at: new Date().toISOString(),
            finished_at: null
          }
        })
      }
      
      // 第 3-4 次调用：检查依赖阶段
      if (progressCallCount <= 4) {
        return Promise.resolve({
          success: true,
          task: {
            task_id: 'task-123',
            plugin_name: 'ComfyUI-Manager',
            github_url: 'https://github.com/ltdrdata/ComfyUI-Manager',
            stage: InstallStage.CHECKING_DEPS,
            progress: 50,
            current_package: '',
            status: InstallStatus.RUNNING,
            error_message: '',
            log_path: '',
            started_at: new Date().toISOString(),
            finished_at: null
          }
        })
      }
      
      // 第 5-6 次调用：安装依赖阶段
      if (progressCallCount <= 6) {
        return Promise.resolve({
          success: true,
          task: {
            task_id: 'task-123',
            plugin_name: 'ComfyUI-Manager',
            github_url: 'https://github.com/ltdrdata/ComfyUI-Manager',
            stage: InstallStage.INSTALLING_DEPS,
            progress: 75,
            current_package: 'numpy',
            status: InstallStatus.RUNNING,
            error_message: '',
            log_path: '',
            started_at: new Date().toISOString(),
            finished_at: null
          }
        })
      }
      
      // 第 7 次及以后：安装成功
      return Promise.resolve({
        success: true,
        task: {
          task_id: 'task-123',
          plugin_name: 'ComfyUI-Manager',
          github_url: 'https://github.com/ltdrdata/ComfyUI-Manager',
          stage: InstallStage.SUCCESS,
          progress: 100,
          current_package: '',
          status: InstallStatus.SUCCESS,
          error_message: '',
          log_path: '',
          started_at: new Date().toISOString(),
          finished_at: new Date().toISOString()
        }
      })
    })
    
    render(<PluginMarketplace />)
    
    // 等待插件列表加载
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
    })
    
    // 步骤 1: 点击安装按钮
    const installButtons = screen.getAllByText('安装')
    const managerInstallBtn = installButtons[0] // 第一个是 ComfyUI-Manager
    await user.click(managerInstallBtn)
    
    // 步骤 2: 验证依赖检查
    await waitFor(() => {
      expect(pluginMarketplaceService.checkDependencies).toHaveBeenCalledWith(
        'https://github.com/ltdrdata/ComfyUI-Manager'
      )
    })
    
    // 步骤 3: 验证安装开始
    await waitFor(() => {
      expect(pluginMarketplaceService.installPlugin).toHaveBeenCalledWith(
        'https://github.com/ltdrdata/ComfyUI-Manager',
        true // autoInstallDeps
      )
    })
    
    // 步骤 4: 验证进度弹窗显示
    await waitFor(() => {
      expect(screen.getByText('安装插件: ComfyUI-Manager')).toBeInTheDocument()
    })
    
    // 步骤 5: 验证克隆阶段
    await waitFor(() => {
      expect(screen.getByText('正在克隆插件...')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // 步骤 6: 验证检查依赖阶段
    await waitFor(() => {
      expect(screen.getByText('正在检查依赖...')).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // 步骤 7: 验证安装依赖阶段
    await waitFor(() => {
      expect(screen.getByText(/正在安装.*numpy/)).toBeInTheDocument()
    }, { timeout: 3000 })
    
    // 步骤 8: 验证安装成功
    await waitFor(() => {
      expect(screen.getByText('安装成功！')).toBeInTheDocument()
    }, { timeout: 5000 })
    
    // 步骤 9: 关闭进度弹窗
    const completeButton = screen.getByRole('button', { name: /完成/i })
    await user.click(completeButton)
    
    // 验证弹窗关闭
    await waitFor(() => {
      expect(screen.queryByText('安装插件: ComfyUI-Manager')).not.toBeInTheDocument()
    })
  })

  /**
   * E2E 测试 3: 搜索和过滤功能
   * 
   * 用户场景：
   * 1. 在插件库中输入搜索关键词
   * 2. 点击查询按钮
   * 3. 查看过滤后的结果
   * 4. 清空搜索关键词
   * 5. 查看完整列表
   */
  it('应该支持搜索和过滤插件', async () => {
    const user = userEvent.setup()
    
    render(<PluginMarketplace />)
    
    // 等待插件列表加载
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
      expect(screen.getByText('ComfyUI-Impact-Pack')).toBeInTheDocument()
    })
    
    // 步骤 1: 输入搜索关键词 "Manager"
    const searchInput = screen.getByPlaceholderText(/搜索插件/i)
    await user.type(searchInput, 'Manager')
    
    // 步骤 2: 点击查询按钮
    const searchButton = screen.getByRole('button', { name: /查询/i })
    await user.click(searchButton)
    
    // 步骤 3: 验证只显示匹配的插件
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
      // Impact-Pack 不应该显示（因为不包含 "Manager"）
      expect(screen.queryByText('ComfyUI-Impact-Pack')).not.toBeInTheDocument()
    })
    
    // 步骤 4: 清空搜索关键词
    await user.clear(searchInput)
    await user.click(searchButton)
    
    // 步骤 5: 验证显示完整列表
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
      expect(screen.getByText('ComfyUI-Impact-Pack')).toBeInTheDocument()
    })
  })

  /**
   * E2E 测试 4: 缓存机制验证
   * 
   * 用户场景：
   * 1. 首次加载插件列表（从 API 获取）
   * 2. 刷新页面或重新打开
   * 3. 从缓存加载插件列表
   * 4. 手动刷新清除缓存
   * 5. 重新从 API 获取
   */
  it('应该正确使用缓存机制', async () => {
    const user = userEvent.setup()
    
    // 首次渲染 - 应该使用缓存
    const { unmount } = render(<PluginMarketplace />)
    
    await waitFor(() => {
      expect(pluginMarketplaceService.getPlugins).toHaveBeenCalledWith(true) // use_cache = true
    })
    
    // 卸载组件
    unmount()
    
    // 重新渲染 - 应该仍然使用缓存
    render(<PluginMarketplace />)
    
    await waitFor(() => {
      expect(pluginMarketplaceService.getPlugins).toHaveBeenCalledWith(true)
    })
    
    // 点击刷新按钮 - 应该清除缓存
    const refreshButton = screen.getByRole('button', { name: /刷新/i })
    await user.click(refreshButton)
    
    await waitFor(() => {
      expect(pluginMarketplaceService.refreshPlugins).toHaveBeenCalled()
    })
  })

  /**
   * E2E 测试 5: 错误场景处理
   * 
   * 用户场景：
   * 1. 网络请求失败
   * 2. 显示错误提示
   * 3. 用户重试操作
   * 4. 安装失败处理
   */
  it('应该正确处理各种错误场景', async () => {
    const user = userEvent.setup()
    
    // 场景 1: 插件列表加载失败
    vi.mocked(pluginMarketplaceService.getPlugins).mockResolvedValueOnce({
      success: false,
      error_message: '网络连接失败，请检查网络设置'
    })
    
    render(<PluginMarketplace />)
    
    // 验证错误提示显示
    await waitFor(() => {
      expect(screen.getByText('网络连接失败，请检查网络设置')).toBeInTheDocument()
    })
    
    // 场景 2: 用户点击刷新重试
    vi.mocked(pluginMarketplaceService.refreshPlugins).mockResolvedValueOnce({
      success: true,
      message: '刷新成功'
    })
    
    vi.mocked(pluginMarketplaceService.getPlugins).mockResolvedValueOnce({
      success: true,
      plugins: [comfyUIManager]
    })
    
    const refreshButton = screen.getByRole('button', { name: /刷新/i })
    await user.click(refreshButton)
    
    // 验证重新加载成功
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
    })
  })

  /**
   * E2E 测试 6: 安装失败场景
   * 
   * 用户场景：
   * 1. 尝试安装插件
   * 2. 安装过程中失败
   * 3. 显示错误信息和日志按钮
   * 4. 用户查看日志
   */
  it('应该正确处理安装失败场景', async () => {
    const user = userEvent.setup()
    
    // Mock 安装失败
    vi.mocked(pluginMarketplaceService.getInstallProgress).mockResolvedValue({
      success: true,
      task: {
        task_id: 'task-123',
        plugin_name: 'ComfyUI-Manager',
        github_url: 'https://github.com/ltdrdata/ComfyUI-Manager',
        stage: InstallStage.FAILED,
        progress: 30,
        current_package: '',
        status: InstallStatus.FAILED,
        error_message: 'Git clone failed: repository not found',
        log_path: '/logs/plugin_install_manager_20240115.log',
        started_at: new Date().toISOString(),
        finished_at: new Date().toISOString()
      }
    })
    
    render(<PluginMarketplace />)
    
    // 等待插件列表加载
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
    })
    
    // 点击安装按钮
    const installButtons = screen.getAllByText('安装')
    await user.click(installButtons[0])
    
    // 等待安装失败
    await waitFor(() => {
      expect(screen.getByText('安装失败')).toBeInTheDocument()
      expect(screen.getByText('Git clone failed: repository not found')).toBeInTheDocument()
    }, { timeout: 5000 })
    
    // 验证查看日志按钮存在
    expect(screen.getByRole('button', { name: /查看日志/i })).toBeInTheDocument()
    
    // 点击关闭按钮
    const closeButton = screen.getByRole('button', { name: /关闭/i })
    await user.click(closeButton)
    
    // 验证弹窗关闭
    await waitFor(() => {
      expect(screen.queryByText('安装失败')).not.toBeInTheDocument()
    })
  })

  /**
   * E2E 测试 7: 依赖冲突警告流程
   * 
   * 用户场景：
   * 1. 尝试安装有依赖冲突的插件
   * 2. 系统检测到冲突并显示警告
   * 3. 用户查看冲突详情
   * 4. 用户选择继续安装或取消
   */
  it('应该正确处理依赖冲突警告', async () => {
    const user = userEvent.setup()
    
    // Mock 依赖冲突
    vi.mocked(pluginMarketplaceService.checkDependencies).mockResolvedValue({
      success: true,
      has_conflicts: true,
      conflicts: [
        {
          package: 'numpy',
          required_version: '>=1.20.0',
          installed_version: '1.19.0',
          conflict_type: 'version_mismatch',
          severity: 'error'
        },
        {
          package: 'torch',
          required_version: '==2.0.0',
          installed_version: '1.13.0',
          conflict_type: 'version_mismatch',
          severity: 'warning'
        }
      ]
    })
    
    render(<PluginMarketplace />)
    
    // 等待插件列表加载
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
    })
    
    // 点击安装按钮
    const installButtons = screen.getAllByText('安装')
    await user.click(installButtons[0])
    
    // 等待冲突警告显示
    await waitFor(() => {
      expect(screen.getByText('检测到依赖冲突')).toBeInTheDocument()
      expect(screen.getByText(/检测到 2 个依赖冲突/)).toBeInTheDocument()
    })
    
    // 验证冲突详情显示
    expect(screen.getByText('numpy')).toBeInTheDocument()
    expect(screen.getByText('torch')).toBeInTheDocument()
    
    // 验证按钮存在
    expect(screen.getByRole('button', { name: /取消/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /继续安装/i })).toBeInTheDocument()
    
    // 场景 A: 用户选择取消
    const cancelButton = screen.getByRole('button', { name: /取消/i })
    await user.click(cancelButton)
    
    // 验证弹窗关闭
    await waitFor(() => {
      expect(screen.queryByText('检测到依赖冲突')).not.toBeInTheDocument()
    })
  })

  /**
   * E2E 测试 8: 自动安装依赖开关功能
   * 
   * 用户场景：
   * 1. 查看自动安装依赖开关状态
   * 2. 切换开关
   * 3. 安装插件时使用新的设置
   */
  it('应该正确处理自动安装依赖开关', async () => {
    const user = userEvent.setup()
    
    render(<PluginMarketplace />)
    
    // 验证开关默认开启
    const switchElement = screen.getByTestId('auto-install-switch')
    expect(switchElement).toBeChecked()
    
    // 关闭自动安装依赖
    await user.click(switchElement)
    
    await waitFor(() => {
      expect(switchElement).not.toBeChecked()
    })
    
    // 等待插件列表加载
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
    })
    
    // 点击安装按钮
    const installButtons = screen.getAllByText('安装')
    await user.click(installButtons[0])
    
    // 验证安装时使用了正确的 autoInstallDeps 参数
    await waitFor(() => {
      expect(pluginMarketplaceService.installPlugin).toHaveBeenCalledWith(
        'https://github.com/ltdrdata/ComfyUI-Manager',
        false // autoInstallDeps = false
      )
    })
  })

  /**
   * E2E 测试 9: GitHub 直接安装功能
   * 
   * 用户场景：
   * 1. 在 GitHub 地址输入框输入仓库地址
   * 2. 点击安装按钮
   * 3. 系统验证 URL 格式
   * 4. 开始安装流程
   */
  it('应该支持从 GitHub 地址直接安装插件', async () => {
    const user = userEvent.setup()
    
    // Mock 成功的安装流程
    vi.mocked(pluginMarketplaceService.getInstallProgress).mockResolvedValue({
      success: true,
      task: {
        task_id: 'task-456',
        plugin_name: 'Custom-Plugin',
        github_url: 'https://github.com/custom/custom-plugin',
        stage: InstallStage.SUCCESS,
        progress: 100,
        current_package: '',
        status: InstallStatus.SUCCESS,
        error_message: '',
        log_path: '',
        started_at: new Date().toISOString(),
        finished_at: new Date().toISOString()
      }
    })
    
    render(<PluginMarketplace />)
    
    // 等待页面加载
    await waitFor(() => {
      expect(screen.getByText('插件市场')).toBeInTheDocument()
    })
    
    // 找到 GitHub 地址输入框
    const githubInput = screen.getByPlaceholderText(/GitHub 仓库地址/i)
    
    // 输入有效的 GitHub URL
    await user.type(githubInput, 'https://github.com/custom/custom-plugin')
    
    // 找到 GitHub 安装按钮（不是插件卡片的安装按钮）
    const buttons = screen.getAllByRole('button', { name: /安装/i })
    const githubInstallButton = buttons.find(btn => 
      btn.getAttribute('data-variant') === 'secondary'
    )
    
    expect(githubInstallButton).toBeDefined()
    await user.click(githubInstallButton!)
    
    // 验证依赖检查被调用
    await waitFor(() => {
      expect(pluginMarketplaceService.checkDependencies).toHaveBeenCalledWith(
        'https://github.com/custom/custom-plugin'
      )
    })
    
    // 验证安装被调用
    await waitFor(() => {
      expect(pluginMarketplaceService.installPlugin).toHaveBeenCalledWith(
        'https://github.com/custom/custom-plugin',
        true
      )
    })
    
    // 验证安装成功
    await waitFor(() => {
      expect(screen.getByText('安装成功！')).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  /**
   * E2E 测试 10: 并发安装控制
   * 
   * 用户场景：
   * 1. 开始安装第一个插件
   * 2. 尝试安装第二个插件
   * 3. 系统阻止并发安装
   * 4. 第一个安装完成后可以安装新插件
   */
  it('应该阻止同时安装多个插件', async () => {
    const user = userEvent.setup()
    
    // Mock 长时间运行的安装
    let installComplete = false
    vi.mocked(pluginMarketplaceService.getInstallProgress).mockImplementation(() => {
      if (!installComplete) {
        return Promise.resolve({
          success: true,
          task: {
            task_id: 'task-123',
            plugin_name: 'ComfyUI-Manager',
            github_url: 'https://github.com/ltdrdata/ComfyUI-Manager',
            stage: InstallStage.CLONING,
            progress: 30,
            current_package: '',
            status: InstallStatus.RUNNING,
            error_message: '',
            log_path: '',
            started_at: new Date().toISOString(),
            finished_at: null
          }
        })
      }
      
      return Promise.resolve({
        success: true,
        task: {
          task_id: 'task-123',
          plugin_name: 'ComfyUI-Manager',
          github_url: 'https://github.com/ltdrdata/ComfyUI-Manager',
          stage: InstallStage.SUCCESS,
          progress: 100,
          current_package: '',
          status: InstallStatus.SUCCESS,
          error_message: '',
          log_path: '',
          started_at: new Date().toISOString(),
          finished_at: new Date().toISOString()
        }
      })
    })
    
    render(<PluginMarketplace />)
    
    // 等待插件列表加载
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
      expect(screen.getByText('ComfyUI-Impact-Pack')).toBeInTheDocument()
    })
    
    // 开始安装第一个插件
    const installButtons = screen.getAllByText('安装')
    await user.click(installButtons[0]) // ComfyUI-Manager
    
    // 等待安装开始
    await waitFor(() => {
      expect(screen.getByText('正在克隆插件...')).toBeInTheDocument()
    })
    
    // 验证其他安装按钮被禁用
    const allInstallButtons = screen.getAllByText('安装')
    allInstallButtons.forEach(btn => {
      expect(btn).toBeDisabled()
    })
    
    // 验证刷新按钮被禁用
    const refreshButton = screen.getByRole('button', { name: /刷新/i })
    expect(refreshButton).toBeDisabled()
    
    // 验证自动安装依赖开关被禁用
    const switchElement = screen.getByTestId('auto-install-switch')
    expect(switchElement).toBeDisabled()
    
    // 完成安装
    installComplete = true
    
    // 关闭进度弹窗
    await waitFor(() => {
      expect(screen.getByText('安装成功！')).toBeInTheDocument()
    }, { timeout: 5000 })
    
    const completeButton = screen.getByRole('button', { name: /完成/i })
    await user.click(completeButton)
    
    // 验证按钮重新启用
    await waitFor(() => {
      const installButtons = screen.getAllByText('安装')
      installButtons.forEach(btn => {
        if (!btn.closest('[data-plugin-name="ComfyUI-Impact-Pack"]')) {
          // Impact-Pack 已安装，其按钮应该保持禁用
          expect(btn).not.toBeDisabled()
        }
      })
    })
  })

  /**
   * E2E 测试 11: 选项卡切换保持状态
   * 
   * 用户场景：
   * 1. 在插件库中进行搜索
   * 2. 切换到新手推荐
   * 3. 切换回插件库
   * 4. 验证搜索状态保持
   */
  it('应该在选项卡切换时保持状态', async () => {
    const user = userEvent.setup()
    
    render(<PluginMarketplace />)
    
    // 等待插件列表加载
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
    })
    
    // 在插件库中进行搜索
    const searchInput = screen.getByPlaceholderText(/搜索插件/i)
    await user.type(searchInput, 'Manager')
    
    const searchButton = screen.getByRole('button', { name: /查询/i })
    await user.click(searchButton)
    
    // 验证搜索结果
    await waitFor(() => {
      expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
      expect(screen.queryByText('Plugin-1')).not.toBeInTheDocument()
    })
    
    // 切换到新手推荐
    const recommendedTab = screen.getByTestId('tab-trigger-recommended')
    await user.click(recommendedTab)
    
    await waitFor(() => {
      expect(screen.getByTestId('tab-content-recommended')).toBeInTheDocument()
    })
    
    // 切换回插件库
    const libraryTab = screen.getByTestId('tab-trigger-library')
    await user.click(libraryTab)
    
    await waitFor(() => {
      expect(screen.getByTestId('tab-content-library')).toBeInTheDocument()
    })
    
    // 验证搜索关键词仍然存在
    expect(searchInput).toHaveValue('Manager')
    
    // 验证搜索结果仍然是过滤后的
    expect(screen.getByText('ComfyUI-Manager')).toBeInTheDocument()
  })
})
