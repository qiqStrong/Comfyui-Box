import { describe, it, expect } from 'vitest'

import { convertToReactFlow, getWorkflowStats } from '@/utils/workflowParser'
import type { WorkflowJsonData } from '@/types/workflow'

/**
 * 工作流目录里允许出现结构不完整或格式不同的 JSON。
 * 这些用例锁死"解析不抛异常"这条底线——一旦抛异常，整个工作流页会掉进路由错误边界。
 */
describe('workflowParser 对异常结构的容错', () => {
  it('API 格式（没有 nodes 字段）不抛异常，返回空图', () => {
    const apiFormat = {
      '3': { class_type: 'KSampler', inputs: { seed: 1 } },
      '4': { class_type: 'VAEDecode', inputs: {} }
    } as unknown as WorkflowJsonData

    expect(() => convertToReactFlow(apiFormat)).not.toThrow()
    expect(convertToReactFlow(apiFormat)).toEqual({ nodes: [], edges: [] })

    const stats = getWorkflowStats(apiFormat)
    expect(stats.totalNodes).toBe(0)
    expect(stats.totalLinks).toBe(0)
    expect(stats.plugins).toEqual([])
  })

  it('nodes 不是数组时不抛异常', () => {
    const broken = { nodes: null, links: null } as unknown as WorkflowJsonData

    expect(() => convertToReactFlow(broken)).not.toThrow()
    expect(convertToReactFlow(broken).nodes).toEqual([])
    expect(getWorkflowStats(broken).totalNodes).toBe(0)
  })

  it('节点缺少 pos / size 时用默认值兜底', () => {
    const data = {
      nodes: [{ id: 1, type: 'KSampler' }],
      links: []
    } as unknown as WorkflowJsonData

    const { nodes } = convertToReactFlow(data)
    expect(nodes).toHaveLength(1)
    expect(nodes[0].position).toEqual({ x: 0, y: 0 })
  })

  it('空图返回 0 节点 0 连线', () => {
    const empty = { nodes: [], links: [] } as unknown as WorkflowJsonData

    expect(convertToReactFlow(empty)).toEqual({ nodes: [], edges: [] })
    expect(getWorkflowStats(empty)).toMatchObject({ totalNodes: 0, totalLinks: 0 })
  })
})
