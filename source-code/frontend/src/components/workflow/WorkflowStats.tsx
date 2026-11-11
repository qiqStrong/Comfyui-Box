/**
 * 工作流统计数据展示组件
 */

import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

interface WorkflowStatsProps {
  totalNodes: number
  totalLinks: number
  nodeTypesCount: number
  pluginsCount: number
  /** 被排除的虚拟节点数（Reroute / Note），用于解释节点图里多出来的方块 */
  virtualNodes?: number
  className?: string
}

export function WorkflowStats({
  totalNodes,
  totalLinks,
  nodeTypesCount,
  pluginsCount,
  virtualNodes = 0,
  className
}: WorkflowStatsProps) {
  const { t } = useTranslation()

  const stats = [
    { label: t('workflow.stats.nodes'), value: totalNodes },
    { label: t('workflow.stats.links'), value: totalLinks },
    { label: t('workflow.stats.types'), value: nodeTypesCount },
    { label: t('workflow.stats.plugins'), value: pluginsCount }
  ]

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="grid grid-cols-4 gap-2">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="flex flex-col items-center justify-center rounded border border-border-subtle bg-surface-active p-2"
          >
            <div className="mb-1 text-lg font-bold leading-none font-mono text-foreground">
              {stat.value}
            </div>
            <div className="text-[10px] text-muted-foreground">{stat.label}</div>
          </div>
        ))}
      </div>
      {virtualNodes > 0 && (
        <p className="text-[10px] leading-tight text-muted-foreground">
          {t('workflow.stats.virtualHint', { count: virtualNodes })}
        </p>
      )}
    </div>
  )
}
