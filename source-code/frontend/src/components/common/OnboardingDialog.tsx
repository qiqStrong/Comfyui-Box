/**
 * 首启引导弹窗
 *
 * - 无注册表且无旧数据：给「新建」或「导入索引」，不静默创建空库；
 * - 用户数据指针失效：进入只读引导，提供重新定位。
 */

import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { FolderSearch, Import, Plus } from 'lucide-react'
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
import type { ManifestPreview, OnboardingState } from '@/types/bridge'
import { toast } from '@/utils/toast'

export function OnboardingDialog() {
  const { t } = useTranslation()
  const [state, setState] = useState<OnboardingState | null>(null)
  const [busy, setBusy] = useState(false)
  const [preview, setPreview] = useState<ManifestPreview | null>(null)
  const [content, setContent] = useState('')
  const fileRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      if (!window.pywebview?.api) return
      try {
        const response = await window.pywebview.api.onboarding_get_state()
        if (!cancelled && response?.success) setState(response)
      } catch (error) {
        console.error('[onboarding] 读取状态失败:', error)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  if (!state?.needs_onboarding) return null

  const createNew = async () => {
    setBusy(true)
    try {
      const response = await window.pywebview.api.userdata_initialize(null)
      if (!response.success) {
        toast.error(response.error || t('onboarding.createFailed'))
        return
      }
      toast.success(t('onboarding.createDone'))
      await window.pywebview.api.userdata_restart_app()
    } finally {
      setBusy(false)
    }
  }

  const chooseAndRelocate = async () => {
    setBusy(true)
    try {
      const folder = await window.pywebview.api.browse_folder_for_shortcut()
      if (!folder.success || !folder.path) {
        if (folder.error_message) toast.error(folder.error_message)
        return
      }
      const response = await window.pywebview.api.onboarding_relocate(folder.path)
      if (!response.success) {
        toast.error(response.error || t('onboarding.relocateFailed'))
        return
      }
      toast.success(t('onboarding.relocateDone'))
      await window.pywebview.api.userdata_restart_app()
    } finally {
      setBusy(false)
    }
  }

  const pickManifest = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setBusy(true)
    try {
      const text = await file.text()
      const result = await window.pywebview.api.manifest_preview_import(text)
      if (!result.success) {
        toast.error(result.error || result.validation?.errors?.[0] || t('onboarding.previewFailed'))
        return
      }
      setContent(text)
      setPreview(result)
    } finally {
      setBusy(false)
    }
  }

  const importManifest = async () => {
    if (!content) return
    setBusy(true)
    try {
      const result = await window.pywebview.api.manifest_import(content, { overwrite: false, update_pointer: false })
      if (!result.success) {
        toast.error(result.error || t('onboarding.importFailed'))
        return
      }
      toast.success(t('onboarding.importDone', { roots: result.applied?.roots ?? 0 }))
      await window.pywebview.api.userdata_restart_app()
    } finally {
      setBusy(false)
    }
  }

  const readonly = state.mode === 'readonly_relocate'

  return (
    <>
      <AlertDialog open>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{readonly ? t('onboarding.relocateTitle') : t('onboarding.title')}</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <span className="block">{state.message}</span>
              <span className="block break-all font-mono text-xs">{state.userdata_root}</span>
              {state.runtime_isolated && (
                <span className="block text-xs text-amber-600">{t('onboarding.isolated')}</span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            {readonly ? (
              <>
                <AlertDialogCancel disabled={busy}>{t('onboarding.later')}</AlertDialogCancel>
                <AlertDialogAction onClick={chooseAndRelocate} disabled={busy}>
                  <FolderSearch className="mr-1 size-4" />
                  {t('onboarding.relocate')}
                </AlertDialogAction>
              </>
            ) : (
              <>
                <AlertDialogCancel onClick={createNew} disabled={busy}>
                  <Plus className="mr-1 size-4" />
                  {t('onboarding.create')}
                </AlertDialogCancel>
                <AlertDialogAction onClick={() => fileRef.current?.click()} disabled={busy}>
                  <Import className="mr-1 size-4" />
                  {t('onboarding.import')}
                </AlertDialogAction>
              </>
            )}
          </AlertDialogFooter>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={pickManifest}
          />
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!preview} onOpenChange={(open) => { if (!open) setPreview(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('settings.storage.manifest.previewTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <span className="block max-h-56 overflow-auto rounded-md border border-border p-2 text-xs">
                {preview?.items?.map((item) => (
                  <span key={`${item.kind}-${item.id}`} className="block">
                    {item.name || item.id} · {item.status} {item.reason ? `· ${item.reason}` : ''}
                  </span>
                ))}
              </span>
              <span className="block text-xs text-muted-foreground">{t('settings.storage.manifest.importHint')}</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>{t('common.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={importManifest} disabled={busy}>
              {t('settings.storage.manifest.importConfirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
