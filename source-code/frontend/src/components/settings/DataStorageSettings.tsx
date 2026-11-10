/**
 * 数据目录设置组件
 *
 * 用户级数据（资产/提示词/工作流元数据/对话/密钥/配置/备份）保存在机器级
 * 用户数据根，可迁移、可清理；运行级数据（日志/缓存/WebView2）默认放在项目
 * 相对路径，可指定其他可写目录；系统级产物随安装目录存在。
 */

import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowRightLeft, Copy, Database, Download, FileJson, FolderOpen, HardDrive, Layers, RefreshCw, RotateCw, ShieldAlert, Trash2, Upload } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent, Button, Progress } from '@/components/ui'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import type {
  ManifestImportResult,
  ManifestPreview,
  ScopeMatrix,
  ScopePreview,
  UserDataMigrationStatus,
  UserDataRootInspection,
  UserDataStatus,
} from '@/types/bridge'
import { toast } from '@/utils/toast'

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export function DataStorageSettings() {
  const { t } = useTranslation()
  const [status, setStatus] = useState<UserDataStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [migrating, setMigrating] = useState(false)
  const [progress, setProgress] = useState<UserDataMigrationStatus | null>(null)
  const [pendingPath, setPendingPath] = useState<string | null>(null)
  const [pendingInspect, setPendingInspect] = useState<UserDataRootInspection | null>(null)
  const [showChangeDialog, setShowChangeDialog] = useState(false)
  const [showWipeDialog, setShowWipeDialog] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  // 数据范围开关（scopeMap）
  const [scopeMatrix, setScopeMatrix] = useState<ScopeMatrix | null>(null)
  const [scopePreview, setScopePreview] = useState<ScopePreview | null>(null)
  const [pendingScope, setPendingScope] = useState<{ category: string; rootId: string; mode: string } | null>(null)
  const [customSpaceId, setCustomSpaceId] = useState<string>('')

  // 索引文件（manifest）
  const [manifestPreview, setManifestPreview] = useState<ManifestPreview | null>(null)
  const [manifestContent, setManifestContent] = useState<string>('')
  const [manifestBusy, setManifestBusy] = useState(false)
  const manifestInputRef = useRef<HTMLInputElement | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      if (!window.pywebview?.api) return
      const data = await window.pywebview.api.userdata_get_status()
      setStatus(data)
      const matrix = await window.pywebview.api.scope_get_matrix()
      if (matrix?.success) setScopeMatrix(matrix)
    } catch (error) {
      console.error('[数据目录] 加载状态失败:', error)
      toast.error(t('settings.storage.loadError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const sourceLabel = (source?: string) => {
    switch (source) {
      case 'pointer':
        return t('settings.storage.sourcePointer')
      case 'default':
        return t('settings.storage.sourceDefault')
      case 'fallback':
        return t('settings.storage.sourceFallback')
      default:
        return '—'
    }
  }

  const runMigration = async (sourceRoot: string, targetRoot?: string) => {
    if (!window.pywebview?.api) return null
    setMigrating(true)
    setResult(null)
    try {
      const start = await window.pywebview.api.userdata_start_migration(sourceRoot, targetRoot)
      if (!start.success) {
        toast.error(start.error || t('settings.storage.migrateFailed'))
        return null
      }
      let state: UserDataMigrationStatus | null = null
      while (true) {
        await sleep(600)
        state = await window.pywebview.api.userdata_migration_status()
        setProgress(state)
        if (!state.running) break
      }
      if (state?.result?.success) {
        const kv = state.result.key_verification
        const dc = state.result.dest_counts
        const keyText = kv && kv.encrypted_keys > 0
          ? t('settings.storage.keyVerified', { decrypted: kv.decrypted, total: kv.encrypted_keys })
          : t('settings.storage.keySkipped')
        setResult(t('settings.storage.migrateSummary', {
          files: state.result.copied_files ?? 0,
          assets: dc?.assets ?? 0,
          categories: dc?.categories ?? 0,
          promptImages: dc?.prompt_images ?? 0,
          workflows: dc?.workflows_files ?? 0,
          key: keyText,
        }))
        toast.success(t('settings.storage.migrateDone'))
      } else {
        toast.error(state?.result?.error || t('settings.storage.migrateFailed'))
      }
      await load()
      // 迁移会改动正在使用的数据文件，必须重启后生效
      setStatus((prev) => (prev ? { ...prev, restart_required: true } : prev))
      return state?.result ?? null
    } catch (error) {
      console.error('[数据目录] 迁移失败:', error)
      toast.error(t('settings.storage.migrateFailed'))
      return null
    } finally {
      setMigrating(false)
    }
  }

  const chooseFolder = async (): Promise<string | null> => {
    if (!window.pywebview?.api) return null
    const response = await window.pywebview.api.browse_folder_for_shortcut()
    if (response.success && response.path) return response.path
    if (response.error_message) toast.error(response.error_message)
    return null
  }

  const handleChangeDir = async () => {
    if (!window.pywebview?.api) return
    try {
      const path = await chooseFolder()
      if (!path) return
      const inspection = await window.pywebview.api.userdata_inspect_root(path)
      setPendingInspect(inspection.success ? inspection : null)
      setPendingPath(path)
      setShowChangeDialog(true)
    } catch (error) {
      console.error('[数据目录] 选择目录失败:', error)
      toast.error(t('settings.storage.chooseFailed'))
    }
  }

  const handleMigrateToNewDir = async () => {
    if (!window.pywebview?.api || !status) return
    try {
      const path = await chooseFolder()
      if (!path) return
      const migration = await runMigration(status.root, path)
      if (!migration?.success) return
      toast.success(t('settings.storage.restarting'))
      await window.pywebview.api.userdata_restart_app()
    } catch (error) {
      console.error('[数据目录] 迁移到新目录失败:', error)
      toast.error(t('settings.storage.migrateFailed'))
    }
  }

  const confirmChangeDir = async (withData: boolean) => {
    if (!window.pywebview?.api || !pendingPath || !status) return
    setShowChangeDialog(false)
    if (withData) {
      // 迁移成功后后端会同时写入机器级指针，重启即可生效
      const migration = await runMigration(status.root, pendingPath)
      if (!migration?.success) return
      setPendingPath(null)
      toast.success(t('settings.storage.restarting'))
      await window.pywebview.api.userdata_restart_app()
      return
    }
    const changed = await window.pywebview.api.userdata_set_root(pendingPath, false)
    if (!changed.success) {
      toast.error(changed.error || t('settings.storage.changeFailed'))
      return
    }
    setPendingPath(null)
    toast.success(t('settings.storage.restarting'))
    await window.pywebview.api.userdata_restart_app()
  }

  const runtimeSourceLabel = (source?: string) => {
    switch (source) {
      case 'override':
        return t('settings.storage.runtimeOverride')
      case 'fallback':
        return t('settings.storage.runtimeFallback')
      default:
        return t('settings.storage.runtimeDefault')
    }
  }

  const setRuntimeDir = async (path: string) => {
    if (!window.pywebview?.api) return
    const response = await window.pywebview.api.userdata_set_runtime_dir(path)
    if (!response.success) {
      toast.error(response.error || t('settings.storage.runtimeFailed'))
      return
    }
    toast.success(t('settings.storage.runtimeChanged'))
    await load()
    await window.pywebview.api.userdata_restart_app()
  }

  const handleChangeRuntimeDir = async () => {
    const path = await chooseFolder()
    if (!path) return
    await setRuntimeDir(path)
  }

  const handleResetRuntimeDir = async () => {
    await setRuntimeDir('')
  }

  const handleCopyPath = async () => {
    if (!status?.root) return
    try {
      await navigator.clipboard.writeText(status.root)
      toast.success(t('settings.storage.copied'))
    } catch (error) {
      console.error('[数据目录] 复制路径失败:', error)
      toast.error(t('settings.storage.copyFailed'))
    }
  }

  const confirmWipe = async () => {
    setShowWipeDialog(false)
    if (!window.pywebview?.api) return
    const response = await window.pywebview.api.userdata_wipe_business()
    if (!response.success) {
      toast.error(response.error || t('settings.storage.wipeFailed'))
      return
    }
    toast.success(t('settings.storage.wipeQueued'))
    await window.pywebview.api.userdata_restart_app()
  }

  const handleCleanCache = async () => {
    if (!window.pywebview?.api) return
    const response = await window.pywebview.api.userdata_clean_cache(['cache', 'logs'])
    if (!response.success) {
      toast.error(t('settings.storage.cleanFailed'))
      return
    }
    const deleted = Object.values(response.deleted || {}).reduce((a, b) => a + b, 0)
    toast.success(t('settings.storage.cleanDone', { count: deleted }))
    await load()
  }

  const handleOpenFolder = async (path?: string) => {
    if (!window.pywebview?.api) return
    await window.pywebview.api.userdata_open_folder(path)
  }

  const requestScopeChange = async (category: string, rootId: string, mode: string) => {
    if (!window.pywebview?.api) return
    try {
      const spaceId = mode === 'custom' ? customSpaceId || null : null
      if (mode === 'custom' && !spaceId) {
        toast.error(t('settings.storage.scope.customNeedSpace'))
        return
      }
      const preview = await window.pywebview.api.scope_preview_change(category, mode, rootId, spaceId)
      if (!preview.success) {
        toast.error(preview.error || t('settings.storage.scope.previewFailed'))
        return
      }
      setScopePreview(preview)
      setPendingScope({ category, rootId, mode })
    } catch (error) {
      console.error('[scope] 预览失败:', error)
      toast.error(t('settings.storage.scope.previewFailed'))
    }
  }

  const confirmScopeChange = async () => {
    if (!window.pywebview?.api || !pendingScope) return
    const { category, rootId, mode } = pendingScope
    setPendingScope(null)
    setScopePreview(null)
    try {
      const response = await window.pywebview.api.scope_set(
        category,
        mode,
        rootId,
        mode === 'custom' ? customSpaceId || null : null
      )
      if (!response.success) {
        toast.error(response.error || t('settings.storage.scope.setFailed'))
        return
      }
      if (response.matrix) setScopeMatrix(response.matrix)
      toast.success(t('settings.storage.scope.setDone'))
    } catch (error) {
      console.error('[scope] 切换失败:', error)
      toast.error(t('settings.storage.scope.setFailed'))
    }
  }

  const handleExportManifest = async () => {
    if (!window.pywebview?.api) return
    try {
      const response = await window.pywebview.api.manifest_export()
      if (!response.success || !response.json) {
        toast.error(response.error || t('settings.storage.manifest.exportFailed'))
        return
      }
      const blob = new Blob([response.json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = response.suggested_filename || 'comfyui-box-manifest.json'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      setTimeout(() => URL.revokeObjectURL(url), 2000)
      toast.success(t('settings.storage.manifest.exportDone'))
    } catch (error) {
      console.error('[manifest] 导出失败:', error)
      toast.error(t('settings.storage.manifest.exportFailed'))
    }
  }

  const handleManifestFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || !window.pywebview?.api) return
    setManifestBusy(true)
    try {
      const content = await file.text()
      const preview = await window.pywebview.api.manifest_preview_import(content)
      if (!preview.success) {
        toast.error(preview.error || preview.validation?.errors?.[0] || t('settings.storage.manifest.previewFailed'))
        return
      }
      setManifestContent(content)
      setManifestPreview(preview)
    } catch (error) {
      console.error('[manifest] 读取失败:', error)
      toast.error(t('settings.storage.manifest.previewFailed'))
    } finally {
      setManifestBusy(false)
    }
  }

  const confirmManifestImport = async () => {
    if (!window.pywebview?.api || !manifestContent) return
    setManifestBusy(true)
    try {
      const response: ManifestImportResult = await window.pywebview.api.manifest_import(manifestContent, {
        overwrite: false,
        update_pointer: false,
      })
      if (!response.success) {
        toast.error(response.error || t('settings.storage.manifest.importFailed'))
        return
      }
      toast.success(t('settings.storage.manifest.importDone', { roots: response.applied?.roots ?? 0 }))
      setManifestPreview(null)
      setManifestContent('')
      await load()
    } catch (error) {
      console.error('[manifest] 导入失败:', error)
      toast.error(t('settings.storage.manifest.importFailed'))
    } finally {
      setManifestBusy(false)
    }
  }

  const counts = status?.counts
  const legacy = status?.legacy_sources?.[0]
  const percent = progress && progress.total > 0
    ? Math.min(100, Math.round((progress.done / progress.total) * 100))
    : 0

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">{t('settings.storage.title')}</h2>
        <p className="text-sm text-muted-foreground">{t('settings.storage.description')}</p>
      </div>

      {status?.restart_required && (
        <div className="flex items-center justify-between rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
          <span>{t('settings.storage.restartHint')}</span>
          <Button size="sm" onClick={() => window.pywebview?.api.userdata_restart_app()}>
            <RotateCw className="mr-1 size-4" />
            {t('settings.storage.restart')}
          </Button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="size-4" />
            {t('settings.storage.locationTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-1">
              <div className="break-all font-mono text-sm">
                {status?.root || (loading ? t('common.loading') : '—')}
              </div>
              <div className="text-xs text-muted-foreground">
                {t('settings.storage.source')}: {sourceLabel(status?.source)}
                {status?.pointer_target ? ` · ${t('settings.storage.pointer')}: ${status.pointer_target}` : ''}
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={handleCopyPath} disabled={loading || !status}>
                <Copy className="mr-1 size-4" />
                {t('settings.storage.copyPath')}
              </Button>
              <Button variant="outline" size="sm" onClick={() => handleOpenFolder()} disabled={loading}>
                <FolderOpen className="mr-1 size-4" />
                {t('settings.storage.openFolder')}
              </Button>
              <Button variant="outline" size="sm" onClick={load} disabled={loading || migrating}>
                <RefreshCw className="mr-1 size-4" />
                {t('settings.storage.refresh')}
              </Button>
              <Button variant="outline" size="sm" onClick={handleChangeDir} disabled={loading || migrating}>
                {t('settings.storage.changeDir')}
              </Button>
              <Button size="sm" onClick={handleMigrateToNewDir} disabled={loading || migrating}>
                <ArrowRightLeft className="mr-1 size-4" />
                {t('settings.storage.migrateToNew')}
              </Button>
            </div>
          </div>

          {status?.fallback_reason && (
            <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
              {t('settings.storage.fallbackWarning', { reason: status.fallback_reason })}
            </div>
          )}

          {counts && (
            <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3 lg:grid-cols-6">
              {[
                ['assets', counts.assets],
                ['categories', counts.categories],
                ['thumbnails', counts.thumbnails],
                ['promptImages', counts.prompt_images],
                ['workflows', counts.workflows_files],
                ['conversations', Math.max(0, counts.db_topics)],
              ].map(([key, value]) => (
                <div key={String(key)} className="rounded-md border border-border px-3 py-2">
                  <div className="text-xs text-muted-foreground">{t(`settings.storage.counts.${key}`)}</div>
                  <div className="font-semibold">{String(value)}</div>
                </div>
              ))}
            </div>
          )}

          {(migrating || progress) && (
            <div className="space-y-2 rounded-md border border-border p-3">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{t('settings.storage.migrating')} · {progress?.current || ''}</span>
                <span>{progress?.done ?? 0}/{progress?.total ?? 0} ({percent}%)</span>
              </div>
              <Progress value={percent} max={100} />
            </div>
          )}

          {result && (
            <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm">{result}</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="size-4" />
            {t('settings.storage.scope.title')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{t('settings.storage.scope.desc')}</p>

          {scopeMatrix && scopeMatrix.roots.length === 0 && (
            <p className="text-sm text-muted-foreground">{t('settings.storage.scope.noRoots')}</p>
          )}

          {scopeMatrix?.categories.map((category) => (
            <div key={category.key} className="space-y-2 border-t border-border pt-3 first:border-t-0 first:pt-0">
              <div className="text-sm font-medium">{t(`settings.storage.scope.categories.${category.key}`, { defaultValue: category.label })}</div>
              {scopeMatrix.roots.map((root) => {
                const value = scopeMatrix.values[root.id]?.[category.key]
                const currentMode = value?.mode === 'legacy' ? 'global' : value?.mode || 'private'
                return (
                  <div key={root.id} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="w-40 truncate font-mono text-xs" title={root.path}>{root.name}</span>
                    <select
                      className="h-8 rounded-md border border-border bg-background px-2 text-sm"
                      value={currentMode}
                      onChange={(event) => requestScopeChange(category.key, root.id, event.target.value)}
                      disabled={loading || migrating}
                    >
                      <option value="global">{t('settings.storage.scope.global')}</option>
                      <option value="private">{t('settings.storage.scope.private')}</option>
                      <option value="custom">{t('settings.storage.scope.custom')}</option>
                    </select>
                    <span className="min-w-0 flex-1 break-all font-mono text-xs text-muted-foreground" title={value?.path}>
                      {value?.path || '—'}
                      {value && !value.exists ? ` · ${t('settings.storage.scope.missing')}` : ''}
                    </span>
                  </div>
                )
              })}
            </div>
          ))}

          {scopeMatrix && scopeMatrix.non_switchable.length > 0 && (
            <div className="space-y-1 rounded-md border border-border p-3 text-xs text-muted-foreground">
              <div className="font-medium text-foreground">{t('settings.storage.scope.nonSwitchableTitle')}</div>
              {scopeMatrix.non_switchable.map((item) => (
                <div key={item.key}>· {item.label}：{item.reason}</div>
              ))}
            </div>
          )}

          <p className="text-xs text-muted-foreground">{t('settings.storage.scope.hint')}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileJson className="size-4" />
            {t('settings.storage.manifest.title')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">{t('settings.storage.manifest.desc')}</p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={handleExportManifest} disabled={loading || manifestBusy}>
              <Download className="mr-1 size-4" />
              {t('settings.storage.manifest.export')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => manifestInputRef.current?.click()}
              disabled={loading || manifestBusy}
            >
              <Upload className="mr-1 size-4" />
              {t('settings.storage.manifest.import')}
            </Button>
            <input
              ref={manifestInputRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={handleManifestFile}
            />
          </div>
          <p className="text-xs text-muted-foreground">{t('settings.storage.manifest.security')}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="size-4" />
            {t('settings.storage.runtimeTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">{t('settings.storage.runtimeDesc')}</p>
          <div className="break-all font-mono text-sm">{status?.runtime_dir || (loading ? t('common.loading') : '—')}</div>
          <div className="text-xs text-muted-foreground">
            {t('settings.storage.source')}: {runtimeSourceLabel(status?.runtime_source)}
            {status?.runtime_override ? ` · ${status.runtime_override}` : ''}
          </div>

          {status?.runtime_note && (
            <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
              {t('settings.storage.runtimeWarning', { reason: status.runtime_note })}
            </div>
          )}

          <div className="space-y-1 text-xs text-muted-foreground">
            <div className="break-all">{t('settings.storage.runtimePaths.logs')}: {status?.log_dir || '—'}</div>
            <div className="break-all">{t('settings.storage.runtimePaths.cache')}: {status?.cache_dir || '—'}</div>
            <div className="break-all">{t('settings.storage.runtimePaths.webview2')}: {status?.webview2_dir || '—'}</div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={handleChangeRuntimeDir} disabled={loading || migrating}>
              {t('settings.storage.runtimeChange')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleResetRuntimeDir}
              disabled={loading || migrating || !status?.runtime_override}
            >
              {t('settings.storage.runtimeReset')}
            </Button>
            <Button variant="outline" size="sm" onClick={() => handleOpenFolder(status?.runtime_dir)} disabled={loading || !status}>
              <FolderOpen className="mr-1 size-4" />
              {t('settings.storage.openFolder')}
            </Button>
          </div>

          <p className="text-xs text-muted-foreground">{t('settings.storage.runtimeSharedHint')}</p>
        </CardContent>
      </Card>

      {legacy && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="size-4" />
              {t('settings.storage.legacyTitle')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">{t('settings.storage.legacyDesc')}</p>
            <div className="space-y-1 text-sm">
              <div className="break-all font-mono">{legacy.root}</div>
              <div className="text-xs text-muted-foreground">
                {t('settings.storage.legacyCounts', {
                  assets: legacy.counts.assets,
                  categories: legacy.counts.categories,
                  promptImages: legacy.counts.prompt_images,
                  workflows: legacy.counts.workflows_files,
                })}
              </div>
            </div>
            <Button size="sm" onClick={() => runMigration(legacy.root)} disabled={migrating}>
              {t('settings.storage.legacyMigrate')}
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trash2 className="size-4" />
              {t('settings.storage.cacheTitle')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">{t('settings.storage.cacheDesc')}</p>
            <Button variant="outline" size="sm" onClick={handleCleanCache} disabled={loading || migrating}>
              {t('settings.storage.cleanCache')}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <ShieldAlert className="size-4" />
              {t('settings.storage.wipeTitle')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">{t('settings.storage.wipeDesc')}</p>
            <Button variant="destructive" size="sm" onClick={() => setShowWipeDialog(true)} disabled={loading || migrating}>
              {t('settings.storage.wipeButton')}
            </Button>
          </CardContent>
        </Card>
      </div>

      <AlertDialog open={!!scopePreview} onOpenChange={(open) => { if (!open) { setScopePreview(null); setPendingScope(null) } }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('settings.storage.scope.confirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <span className="block">{t('settings.storage.scope.confirmDesc')}</span>
              {scopePreview && (
                <span className="block font-mono text-xs">
                  {t('settings.storage.scope.current')}: {scopePreview.current.path} ({scopePreview.current.items ?? '—'})
                  <br />
                  {t('settings.storage.scope.target')}: {scopePreview.target.path} ({scopePreview.target.items ?? '—'})
                </span>
              )}
              {scopePreview && !scopePreview.target.exists && (
                <span className="block text-amber-600">{t('settings.storage.scope.targetMissing')}</span>
              )}
              {pendingScope?.mode === 'custom' && scopeMatrix && (
                <select
                  className="mt-2 w-full rounded-md border border-border bg-background px-2 py-1 text-sm"
                  value={customSpaceId}
                  onChange={(event) => setCustomSpaceId(event.target.value)}
                >
                  <option value="">{t('settings.storage.scope.chooseSpace')}</option>
                  {scopeMatrix.data_spaces.map((space) => (
                    <option key={space.id} value={space.id}>{space.name} · {space.path}</option>
                  ))}
                </select>
              )}
              <span className="block text-xs text-muted-foreground">{scopePreview?.message}</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmScopeChange}>{t('settings.storage.scope.confirm')}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!manifestPreview} onOpenChange={(open) => { if (!open) setManifestPreview(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('settings.storage.manifest.previewTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <span className="block">{manifestPreview?.message}</span>
              <span className="block text-xs">
                {t('settings.storage.manifest.summary', {
                  ok: manifestPreview?.summary?.ok ?? 0,
                  missing: manifestPreview?.summary?.missing ?? 0,
                  conflict: manifestPreview?.summary?.conflict ?? 0,
                  rootsOk: manifestPreview?.summary?.roots_ok ?? 0,
                  rootsMissing: manifestPreview?.summary?.roots_missing ?? 0,
                  rootsConflict: manifestPreview?.summary?.roots_conflict ?? 0,
                })}
              </span>
              <span className="block max-h-56 overflow-auto rounded-md border border-border p-2 text-xs">
                {manifestPreview?.items?.map((item) => (
                  <span key={`${item.kind}-${item.id}`} className="block">
                    {item.kind === 'space' ? t('settings.storage.manifest.space') : t('settings.storage.manifest.root')} · {item.name || item.id} · {item.status} {item.reason ? `· ${item.reason}` : ''}
                  </span>
                ))}
              </span>
              <span className="block text-xs text-muted-foreground">{t('settings.storage.manifest.importHint')}</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmManifestImport} disabled={manifestBusy}>
              {t('settings.storage.manifest.importConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showChangeDialog} onOpenChange={setShowChangeDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('settings.storage.changeTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <span className="block">{t('settings.storage.changeDesc', { path: pendingPath || '' })}</span>
              {pendingInspect?.has_business && (
                <span className="block text-amber-600">
                  {t('settings.storage.targetHasData', {
                    assets: pendingInspect.counts?.assets ?? 0,
                    categories: pendingInspect.counts?.categories ?? 0,
                    promptImages: pendingInspect.counts?.prompt_images ?? 0,
                  })}
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={() => confirmChangeDir(false)}>
              {t('settings.storage.changeOnly')}
            </AlertDialogAction>
            <AlertDialogAction onClick={() => confirmChangeDir(true)}>
              {t('settings.storage.changeMigrate')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={showWipeDialog} onOpenChange={setShowWipeDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('settings.storage.wipeTitle')}</AlertDialogTitle>
            <AlertDialogDescription>{t('settings.storage.wipeConfirm')}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive text-destructive-foreground" onClick={confirmWipe}>
              {t('settings.storage.wipeConfirmButton')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
