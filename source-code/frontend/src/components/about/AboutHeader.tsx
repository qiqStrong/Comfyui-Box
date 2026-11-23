import { useState, useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Github, RefreshCw, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { useAppUpdateStore } from '@/stores/useAppUpdateStore'
import { useAutoUpdateCheck } from '@/hooks/useAutoUpdateCheck'
import { toast } from '@/utils/toast'
import { GITHUB_RELEASES_URL } from '@/api/githubApi'

import { UpdateDialog } from './UpdateDialog'

interface AboutHeaderProps {
  version: string
}

export function AboutHeader({ version }: AboutHeaderProps) {
  const { t } = useTranslation()
  const [dialogOpen, setDialogOpen] = useState(false)
  const hasAutoOpenedRef = useRef(false)
  const { hasUpdate, hasViewed, markAsViewed } = useAppUpdateStore()
  const { checkForUpdate, isChecking } = useAutoUpdateCheck()

  const showBadge = hasUpdate && !hasViewed

  useEffect(() => {
    if (hasUpdate && !hasViewed && !hasAutoOpenedRef.current) {
      hasAutoOpenedRef.current = true
      setDialogOpen(true)
    }
  }, [hasUpdate, hasViewed])

  const handleDialogOpenChange = useCallback((open: boolean) => {
    setDialogOpen(open)
    if (!open && hasUpdate) {
      markAsViewed()
    }
  }, [hasUpdate, markAsViewed])

  // 手动检查更新：走应用内 API。发现更新时 setHasUpdate 会触发上方 effect 自动弹出
  // UpdateDialog；已是最新/检查失败则给出明确反馈。GitHub 只作为失败时的兜底入口。
  const handleCheckUpdate = useCallback(async () => {
    const result = await checkForUpdate()
    if (result.status === 'uptodate') {
      toast.success(t('update.noUpdate'))
    } else if (result.status === 'error') {
      toast.error(t('update.checkFailed'), {
        description: result.error || t('update.networkError'),
        action: {
          label: t('update.viewOnGitHub'),
          onClick: () => window.open(GITHUB_RELEASES_URL, '_blank', 'noopener,noreferrer')
        }
      })
    }
  }, [checkForUpdate, t])

  return (
    <>
      <header className="flex flex-col justify-between gap-4 border-b border-border pb-4 sm:flex-row sm:items-start">
        <div className="flex items-start gap-4">
          <img
            src="/logo/app-icon.png"
            alt="Comfyui-Box"
            className="size-14"
          />
          <div className="flex flex-col">
            <div className="mb-1 flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-wide text-foreground">
                Comfyui-Box
              </h1>
              <span className="rounded-full border border-primary/20 bg-primary/10 px-2 py-0.5 font-mono text-xs text-primary">
                {version}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => window.open('https://github.com/qiqStrong/Comfyui-Box', '_blank', 'noopener,noreferrer')}
                className="size-7 rounded-md"
                title="GitHub"
              >
                <Github className="size-4" />
              </Button>
            </div>
            <p className="text-sm text-muted-foreground">
              {t('about.subtitle')}
            </p>
          </div>
        </div>
        <div className="relative">
          <Button
            onClick={handleCheckUpdate}
            disabled={isChecking}
            size="sm"
            variant="outline"
            className="flex items-center gap-2"
            title={t('update.checkUpdate')}
          >
            {isChecking ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}
            {isChecking ? t('update.checking') : t('update.checkUpdate')}
          </Button>
          {showBadge && (
            <span className="absolute -right-1 -top-1 size-2.5 animate-pulse rounded-full border-2 border-background bg-success" />
          )}
        </div>
      </header>

      <UpdateDialog 
        open={dialogOpen} 
        onOpenChange={handleDialogOpenChange}
        currentVersion={version}
      />
    </>
  )
}

export default AboutHeader
