/**
 * 业务页数据范围徽标。
 *
 * 只展示当前环境在该数据类别上的 scope 绑定（全局 / 私有 / 自定义），
 * 不提供切换入口（切换统一在系统设置的数据范围矩阵中完成）。
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

interface ScopeBadgeProps {
  category: 'gallery' | 'prompts' | 'ai' | 'workflows' | 'lora'
  className?: string
}

interface BadgeState {
  mode: string
  path: string
  epoch: number
}

export function ScopeBadge({ category, className }: ScopeBadgeProps) {
  const { t } = useTranslation()
  const [state, setState] = useState<BadgeState | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      if (!window.pywebview?.api) return
      try {
        const matrix = await window.pywebview.api.scope_get_matrix()
        if (!matrix?.success || cancelled) return
        const rootId = matrix.current_environment_id || matrix.roots[0]?.id
        const value = rootId ? matrix.values[rootId]?.[category] : undefined
        if (value) setState({ mode: value.mode, path: value.path, epoch: value.epoch })
      } catch (error) {
        console.debug('[scope] 读取徽标失败:', error)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [category])

  if (!state || state.mode === 'legacy') return null

  const label =
    state.mode === 'global'
      ? t('settings.storage.scope.global')
      : state.mode === 'custom'
        ? t('settings.storage.scope.custom')
        : t('settings.storage.scope.private')

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded border border-border-subtle bg-surface-active px-1.5 py-0.5 text-[11px] text-muted-foreground',
        className
      )}
      title={state.path}
    >
      <span className="size-1.5 rounded-full bg-primary/70" />
      {t(`settings.storage.scope.categories.${category}`, { defaultValue: category })} · {label}
    </span>
  )
}
