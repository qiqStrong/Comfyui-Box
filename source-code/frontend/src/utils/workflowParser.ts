/**
 * 工作流解析工具
 * 
 * 参考 ComfyUI-Manager 的实现，使用三层匹配策略：
 * 1. preemption_map 优先匹配（内置节点和优先级覆盖）
 * 2. rext_map 精确匹配（节点到插件列表）
 * 3. nodename_pattern 正则匹配
 * 
 * 使用 GitHub URL 作为唯一插件标识符
 */

import type { Node, Edge } from '@xyflow/react'
import type { WorkflowJsonData, ComfyNode } from '@/types/workflow'
import { workflowApi } from '@/api/workflow'

export interface ParsedWorkflowNode {
  id: number
  type: string
  githubUrl: string
  pluginName: string
  inputs: { name: string; type: string }[]
  outputs: { name: string; type: string }[]
}

export interface ParsedWorkflow {
  nodes: ParsedWorkflowNode[]
  edges: { id: number; source: number; target: number; sourceHandle: string; targetHandle: string; type: string }[]
  plugins: { githubUrl: string; name: string; nodeCount: number }[]
}

const COMFY_CORE_URL = 'https://github.com/comfyanonymous/ComfyUI'

// 虚拟节点类型（不在工作流中显示）
const VIRTUAL_NODE_TYPES = new Set(['Reroute', 'Note', 'MarkdownNote'])

function isVirtualNode(nodeType: string): boolean {
  if (VIRTUAL_NODE_TYPES.has(nodeType)) {
    return true
  }
  if (nodeType.startsWith('workflow/') || nodeType.startsWith('workflow>')) {
    return true
  }
  return false
}

let _preemptionMap: Record<string, string> = {}
let _rextMap: Record<string, string[]> = {}
let _patterns: [string, string][] = []
let _pluginInfo: Record<string, { name: string; github_url: string; node_count: number }> = {}
let _localPlugins: Record<string, { name: string; github_url: string; enabled: boolean }> = {}
let _builtinNodes: Record<string, { category: string; display_name: string; description: string }> = {}
let _cnrIdMap: Record<string, string> = {}
let _isMapLoaded = false
let _isLoadingMap = false
let _compiledPatterns: RegExp[] = []

let _localNodeMap: {
  nodes: Record<string, { nodeType: string; githubUrl: string; pluginName: string }>
  plugins: Record<string, { githubUrl: string | null; v1Count: number; v3Count: number; frontendCount: number }>
} | null = null
let _isLocalMapLoaded = false

export async function loadNodeTypeMap(): Promise<boolean> {
  if (_isMapLoaded) {
    return true
  }
  
  if (_isLoadingMap) {
    return false
  }
  
  _isLoadingMap = true
  
  try {
    const result = await workflowApi.getNodeTypeMap()
    if (result) {
      _preemptionMap = result.preemptionMap
      _rextMap = result.rextMap
      _patterns = result.patterns
      _pluginInfo = result.pluginInfo
      _localPlugins = result.localPlugins || {}
      _builtinNodes = result.builtinNodes || {}
      _cnrIdMap = result.cnrIdMap || {}
      _isMapLoaded = true
      
      _compiledPatterns = _patterns.map(([pattern]) => {
        try {
          return new RegExp(pattern)
        } catch {
          return null
        }
      }).filter((r): r is RegExp => r !== null)
      
      console.log(
        `节点类型映射表加载成功：preemption=${Object.keys(_preemptionMap).length}, ` +
        `rext=${Object.keys(_rextMap).length}, ` +
        `patterns=${_patterns.length}, ` +
        `plugins=${Object.keys(_pluginInfo).length}, ` +
        `localPlugins=${Object.keys(_localPlugins).length}, ` +
        `builtinNodes=${Object.keys(_builtinNodes).length}`
      )
      
      loadLocalNodeMap().catch(() => {})
      
      return true
    }
    return false
  } catch (error) {
    console.error('加载节点类型映射表失败:', error)
    return false
  } finally {
    _isLoadingMap = false
  }
}

export async function loadLocalNodeMap(force: boolean = false): Promise<boolean> {
  // 如果已加载且不强制刷新，直接返回
  if (!force && _isLocalMapLoaded && _localNodeMap) {
    return true
  }
  
  try {
    const result = await workflowApi.getLocalNodeMap()
    if (result && result.success && result.data) {
      _localNodeMap = {
        nodes: result.data.nodes || {},
        plugins: result.data.plugins || {}
      }
      _isLocalMapLoaded = true
      console.log(
        `本地节点映射表加载成功：nodes=${Object.keys(_localNodeMap.nodes).length}, ` +
        `plugins=${Object.keys(_localNodeMap.plugins).length}`
      )
      return true
    }
    return false
  } catch (error) {
    console.error('加载本地节点映射表失败:', error)
    return false
  }
}

export async function scanLocalNodes(force: boolean = false): Promise<{
  success: boolean
  pluginCount: number
  nodeCount: number
  v1Count: number
  v3Count: number
  frontendCount: number
  elapsedSeconds: number
  error?: string
} | null> {
  try {
    const result = await workflowApi.scanLocalNodes(force)
    if (result && result.success) {
      _isLocalMapLoaded = false
      await loadLocalNodeMap()
    }
    return result
  } catch (error) {
    console.error('扫描本地节点失败:', error)
    return {
      success: false,
      pluginCount: 0,
      nodeCount: 0,
      v1Count: 0,
      v3Count: 0,
      frontendCount: 0,
      elapsedSeconds: 0,
      error: String(error)
    }
  }
}

export async function getLocalScanStatus(): Promise<{
  success: boolean
  initialized: boolean
  hasCache: boolean
  needsRescan: boolean
  comfyuiPath?: string
  error?: string
}> {
  try {
    const result = await workflowApi.getLocalScanStatus()
    return result || { success: false, initialized: false, hasCache: false, needsRescan: true }
  } catch (error) {
    console.error('获取本地扫描状态失败:', error)
    return { success: false, initialized: false, hasCache: false, needsRescan: true, error: String(error) }
  }
}

export function getPluginColor(githubUrl: string, pluginName?: string): string {
  // 使用 pluginName 作为颜色 key（本地插件没有 githubUrl）
  const colorKey = pluginName || githubUrl
  
  if (!colorKey) {
    return 'var(--plugin-color-unknown, #9E9E9E)'
  }
  if (colorKey === COMFY_CORE_URL || colorKey === 'ComfyUI Core') {
    return 'var(--plugin-color-core, #4CAF50)'
  }
  
  let hash = 0
  for (let i = 0; i < colorKey.length; i++) {
    hash = ((hash << 5) - hash) + colorKey.charCodeAt(i)
    hash = hash & hash
  }
  const hue = Math.abs(hash) % 360
  return `hsl(${hue}, 70%, 50%)`
}

export function getPluginName(githubUrl: string): string {
  if (_pluginInfo[githubUrl]?.name) {
    return _pluginInfo[githubUrl].name
  }
  if (githubUrl === COMFY_CORE_URL) {
    return 'ComfyUI Core'
  }
  if (!githubUrl) {
    return 'Unknown'
  }
  
  const parts = githubUrl.replace(/\/$/, '').split('/')
  if (parts.length >= 1) {
    return parts[parts.length - 1]
  }
  
  return 'Unknown'
}

interface PluginInfo {
  githubUrl: string
  pluginName: string
}

function resolvePluginInfo(node: ComfyNode): PluginInfo {
  if (_builtinNodes[node.type]) {
    return { githubUrl: COMFY_CORE_URL, pluginName: 'ComfyUI Core' }
  }
  
  if (_localNodeMap?.nodes && _localNodeMap.nodes[node.type]) {
    const localInfo = _localNodeMap.nodes[node.type]
    return {
      githubUrl: localInfo.githubUrl,
      pluginName: localInfo.pluginName || getPluginName(localInfo.githubUrl)
    }
  }
  
  // 模糊匹配：处理 . 和 _ 分隔符差异
  // ComfyUI 在某些情况下会将节点名中的 . 替换为 _
  if (_localNodeMap?.nodes) {
    const normalizedNodeType = node.type.replace(/\./g, '_')
    for (const [key, value] of Object.entries(_localNodeMap.nodes)) {
      const normalizedKey = key.replace(/\./g, '_')
      if (normalizedKey === normalizedNodeType) {
        return {
          githubUrl: value.githubUrl,
          pluginName: value.pluginName || getPluginName(value.githubUrl)
        }
      }
    }
  }
  
  const cnr_id = node.properties?.cnr_id
  
  if (cnr_id === 'comfy-core') {
    return { githubUrl: COMFY_CORE_URL, pluginName: 'ComfyUI Core' }
  }
  
  const preemptionResult = _preemptionMap[node.type]
  if (preemptionResult) {
    return { githubUrl: preemptionResult, pluginName: getPluginName(preemptionResult) }
  }
  
  const rextResult = _rextMap[node.type]
  if (rextResult && rextResult.length > 0) {
    return { githubUrl: rextResult[0], pluginName: getPluginName(rextResult[0]) }
  }
  
  if (cnr_id) {
    if (_cnrIdMap[cnr_id]) {
      return { githubUrl: _cnrIdMap[cnr_id], pluginName: getPluginName(_cnrIdMap[cnr_id]) }
    }
    
    const normalized = normalizeGithubUrl(cnr_id)
    if (normalized) {
      return { githubUrl: normalized, pluginName: getPluginName(normalized) }
    }
    
    let processedCnrId = cnr_id
    if (cnr_id.startsWith('pr-')) {
      processedCnrId = cnr_id.replace(/^pr-/, '').replace(/-\d+$/, '')
    }
    
    const cnrIdLower = processedCnrId.toLowerCase().replace(/[-_]/g, '')
    const MIN_MATCH_LENGTH = 8
    
    for (const [githubUrl, info] of Object.entries(_pluginInfo)) {
      const urlNormalized = githubUrl.toLowerCase().replace(/[-_]/g, '')
      if (urlNormalized.length >= MIN_MATCH_LENGTH && cnrIdLower.includes(urlNormalized)) {
        return { githubUrl, pluginName: getPluginName(githubUrl) }
      }
      if (info.name && info.name.length >= MIN_MATCH_LENGTH) {
        const nameNormalized = info.name.toLowerCase().replace(/[-_]/g, '')
        if (nameNormalized.length >= MIN_MATCH_LENGTH && cnrIdLower.includes(nameNormalized)) {
          return { githubUrl, pluginName: getPluginName(githubUrl) }
        }
      }
    }
    
    for (const [localUrl, localInfo] of Object.entries(_localPlugins)) {
      const urlNormalized = localUrl.toLowerCase().replace(/[-_]/g, '')
      if (urlNormalized.length >= MIN_MATCH_LENGTH && cnrIdLower.includes(urlNormalized)) {
        return { githubUrl: localUrl, pluginName: getPluginName(localUrl) }
      }
      if (localInfo.name && localInfo.name.length >= MIN_MATCH_LENGTH) {
        const nameNormalized = localInfo.name.toLowerCase().replace(/[-_]/g, '')
        if (nameNormalized.length >= MIN_MATCH_LENGTH && cnrIdLower.includes(nameNormalized)) {
          return { githubUrl: localUrl, pluginName: getPluginName(localUrl) }
        }
      }
    }
  }
  
  for (let i = 0; i < _patterns.length; i++) {
    const [, githubUrl] = _patterns[i]
    const regex = _compiledPatterns[i]
    if (regex && regex.test(node.type)) {
      return { githubUrl, pluginName: getPluginName(githubUrl) }
    }
  }
  
  return { githubUrl: '', pluginName: 'Unknown' }
}

export function getPluginGithubUrl(githubUrl: string): string | null {
  return githubUrl || null
}

function resolveGithubUrl(node: ComfyNode): string {
  if (_builtinNodes[node.type]) {
    return COMFY_CORE_URL
  }
  
  if (_localNodeMap?.nodes && _localNodeMap.nodes[node.type]) {
    return _localNodeMap.nodes[node.type].githubUrl
  }
  
  const cnr_id = node.properties?.cnr_id
  
  if (cnr_id === 'comfy-core') {
    return COMFY_CORE_URL
  }
  
  const preemptionResult = _preemptionMap[node.type]
  if (preemptionResult) {
    return preemptionResult
  }
  
  const rextResult = _rextMap[node.type]
  if (rextResult && rextResult.length > 0) {
    return rextResult[0]
  }
  
  if (cnr_id) {
    if (_cnrIdMap[cnr_id]) {
      return _cnrIdMap[cnr_id]
    }
    
    const normalized = normalizeGithubUrl(cnr_id)
    if (normalized) {
      return normalized
    }
    
    let processedCnrId = cnr_id
    if (cnr_id.startsWith('pr-')) {
      processedCnrId = cnr_id.replace(/^pr-/, '').replace(/-\d+$/, '')
    }
    
    const cnrIdLower = processedCnrId.toLowerCase().replace(/[-_]/g, '')
    const MIN_MATCH_LENGTH = 8
    
    for (const [githubUrl, info] of Object.entries(_pluginInfo)) {
      const urlNormalized = githubUrl.toLowerCase().replace(/[-_]/g, '')
      if (urlNormalized.length >= MIN_MATCH_LENGTH && cnrIdLower.includes(urlNormalized)) {
        return githubUrl
      }
      if (info.name && info.name.length >= MIN_MATCH_LENGTH) {
        const nameNormalized = info.name.toLowerCase().replace(/[-_]/g, '')
        if (nameNormalized.length >= MIN_MATCH_LENGTH && cnrIdLower.includes(nameNormalized)) {
          return githubUrl
        }
      }
    }
    
    for (const [localUrl, localInfo] of Object.entries(_localPlugins)) {
      const urlNormalized = localUrl.toLowerCase().replace(/[-_]/g, '')
      if (urlNormalized.length >= MIN_MATCH_LENGTH && cnrIdLower.includes(urlNormalized)) {
        return localUrl
      }
      if (localInfo.name && localInfo.name.length >= MIN_MATCH_LENGTH) {
        const nameNormalized = localInfo.name.toLowerCase().replace(/[-_]/g, '')
        if (nameNormalized.length >= MIN_MATCH_LENGTH && cnrIdLower.includes(nameNormalized)) {
          return localUrl
        }
      }
    }
  }
  
  for (let i = 0; i < _patterns.length; i++) {
    const [, githubUrl] = _patterns[i]
    const regex = _compiledPatterns[i]
    if (regex && regex.test(node.type)) {
      return githubUrl
    }
  }
  
  return ''
}

function normalizeGithubUrl(url: string): string {
  if (!url) return ''
  
  url = url.trim()
  
  // 移除可能存在的反引号包裹（Markdown 格式）
  if (url.startsWith('`') && url.endsWith('`')) {
    url = url.slice(1, -1)
  }
  
  url = url.trim()
  
  // 移除末尾的逗号
  if (url.endsWith(',')) {
    url = url.slice(0, -1)
  }
  
  url = url.trim()
  
  // 检查是否是完整的 URL
  if (url.startsWith('http://') || url.startsWith('https://')) {
    if (url.endsWith('.git')) {
      url = url.slice(0, -4)
    }
    url = url.replace('git@github.com:', 'https://github.com/')
    return url.replace(/\/$/, '')
  }
  
  // 检查是否是 git@ 格式
  if (url.startsWith('git@')) {
    url = url.replace('git@github.com:', 'https://github.com/')
    if (url.endsWith('.git')) {
      url = url.slice(0, -4)
    }
    return url.replace(/\/$/, '')
  }
  
  // 不是完整的 URL，返回空字符串表示需要通过其他方式查找
  return ''
}

export function parseWorkflow(data: WorkflowJsonData): ParsedWorkflow {
  const nodeMap = new Map<number, ParsedWorkflowNode>()
  const pluginMap = new Map<string, { githubUrl: string; name: string; nodeCount: number }>()

  for (const node of data.nodes) {
    if (isVirtualNode(node.type)) {
      continue
    }

    const githubUrl = resolveGithubUrl(node)

    const parsedNode: ParsedWorkflowNode = {
      id: node.id,
      type: node.type,
      githubUrl,
      pluginName: getPluginName(githubUrl),
      inputs: node.inputs?.map(i => ({ name: i.name, type: i.type })) || [],
      outputs: node.outputs?.map(o => ({ name: o.name, type: o.type })) || []
    }

    nodeMap.set(node.id, parsedNode)

    if (!pluginMap.has(githubUrl)) {
      pluginMap.set(githubUrl, {
        githubUrl,
        name: getPluginName(githubUrl),
        nodeCount: 0
      })
    }
    pluginMap.get(githubUrl)!.nodeCount++
  }

  if (data.extra?.groupNodes) {
    for (const groupData of Object.values(data.extra.groupNodes) as { nodes?: ComfyNode[] }[]) {
      const groupNodes = groupData.nodes || []
      for (const node of groupNodes) {
        if (isVirtualNode(node.type)) {
          continue
        }

        const githubUrl = resolveGithubUrl(node)

        if (!pluginMap.has(githubUrl)) {
          pluginMap.set(githubUrl, {
            githubUrl,
            name: getPluginName(githubUrl),
            nodeCount: 0
          })
        }
        pluginMap.get(githubUrl)!.nodeCount++
      }
    }
  }

  const edges: ParsedWorkflow['edges'] = []
  if (data.links) {
    for (const link of data.links) {
      const [id, sourceId, sourceSlot, targetId, targetSlot, type] = link
      edges.push({
        id,
        source: sourceId,
        target: targetId,
        sourceHandle: `output-${sourceSlot}`,
        targetHandle: `input-${targetSlot}`,
        type
      })
    }
  }

  return {
    nodes: Array.from(nodeMap.values()),
    edges,
    plugins: Array.from(pluginMap.values())
  }
}

export function convertToReactFlow(data: WorkflowJsonData): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []

  // 工作流目录里可能混入 API 格式（无 nodes 字段）或结构残缺的文件。
  // 这里不能假设数组存在，否则整个页面会掉进路由错误边界。
  const rawNodes = Array.isArray(data?.nodes) ? data.nodes : []
  const rawLinks = Array.isArray(data?.links) ? data.links : []

  for (const node of rawNodes) {
    const { githubUrl, pluginName } = resolvePluginInfo(node)

    const isReroute = node.type === 'Reroute'
    const position = Array.isArray(node.pos) ? node.pos : [0, 0]
    const size = Array.isArray(node.size) ? node.size : [200, 80]

    nodes.push({
      id: String(node.id),
      type: 'workflowNode',
      position: { x: position[0], y: position[1] },
      data: {
        label: node.type,
        nodeType: node.type,
        githubUrl,
        pluginName,
        pluginColor: getPluginColor(githubUrl, pluginName),
        inputs: node.inputs || [],
        outputs: node.outputs || [],
        isReroute
      },
      style: isReroute ? {
        width: size[0],
        height: size[1],
      } : undefined
    })
  }

  if (rawLinks.length) {
    for (const link of rawLinks) {
      const [id, sourceId, sourceSlot, targetId, targetSlot, linkType] = link

      const sourceNode = rawNodes.find(n => n.id === sourceId)
      const targetNode = rawNodes.find(n => n.id === targetId)
      
      if (!sourceNode || !targetNode) {
        console.warn(`Link ${id}: source node ${sourceId} or target node ${targetId} not found`)
        continue
      }
      
      const sourceOutput = sourceNode.outputs?.[sourceSlot]
      const targetInput = targetNode.inputs?.[targetSlot]
      
      if (!sourceOutput) {
        console.warn(`Link ${id}: source node ${sourceId} output slot ${sourceSlot} not found. Available outputs:`, sourceNode.outputs)
      }
      
      if (!targetInput) {
        console.warn(`Link ${id}: target node ${targetId} input slot ${targetSlot} not found. Available inputs:`, targetNode.inputs)
      }
      
      edges.push({
        id: String(id),
        source: String(sourceId),
        target: String(targetId),
        sourceHandle: `output-${sourceSlot}`,
        targetHandle: `input-${targetSlot}`,
        style: { stroke: getLinkColor(linkType) },
        animated: false
      })
    }
  }

  return { nodes, edges }
}

const LINK_COLORS: Record<string, string> = {
  'IMAGE': 'var(--link-color-image, #4CAF50)',
  'LATENT': 'var(--link-color-latent, #2196F3)',
  'MODEL': 'var(--link-color-model, #FF9800)',
  'CLIP': 'var(--link-color-clip, #9C27B0)',
  'VAE': 'var(--link-color-vae, #00BCD4)',
  'CONDITIONING': 'var(--link-color-cond, #E91E63)',
  'STRING': 'var(--link-color-string, #FFEB3B)',
  'INT': 'var(--link-color-int, #795548)',
  'FLOAT': 'var(--link-color-float, #607D8B)',
  'MASK': 'var(--link-color-mask, #FF5722)'
}

function getLinkColor(type: string): string {
  return LINK_COLORS[type] || 'var(--link-color-default, #9E9E9E)'
}

export function getWorkflowStats(data: WorkflowJsonData) {
  const nodeTypes = new Map<string, number>()
  const plugins = new Map<string, { githubUrl: string; count: number; nodes: string[] }>()

  // 与 convertToReactFlow 保持一致：API 格式或残缺文件没有 nodes 数组
  const rawNodes = Array.isArray(data?.nodes) ? data.nodes : []

  // 节点数与后端 extract_node_count 同口径：排除 Reroute / Note，
  // 保证列表卡片和详情面板显示的是同一个数字
  let totalNodes = 0
  let virtualNodes = 0

  // API 格式（顶层没有 nodes 数组）画不出节点图，但节点本身是存在的。
  // 这里同样按 class_type 条目计数，否则会出现"卡片 2 节点、详情 0 节点"。
  if (!Array.isArray(data?.nodes)) {
    for (const value of Object.values(data ?? {})) {
      const classType = (value as { class_type?: unknown } | null)?.class_type
      if (typeof classType !== 'string') continue
      totalNodes++
      nodeTypes.set(classType, (nodeTypes.get(classType) || 0) + 1)
    }
    return {
      totalNodes,
      virtualNodes: 0,
      isApiFormat: totalNodes > 0,
      totalLinks: 0,
      nodeTypes: Array.from(nodeTypes.entries()).map(([type, count]) => ({ type, count })),
      plugins: []
    }
  }

  for (const node of rawNodes) {
    if (isVirtualNode(node.type)) {
      virtualNodes++
      continue
    }
    totalNodes++
    
    nodeTypes.set(node.type, (nodeTypes.get(node.type) || 0) + 1)
    
    const { githubUrl, pluginName } = resolvePluginInfo(node)
    
    if (!plugins.has(pluginName)) {
      plugins.set(pluginName, { githubUrl, count: 0, nodes: [] })
    }
    const plugin = plugins.get(pluginName)!
    plugin.count++
    if (!plugin.nodes.includes(node.type)) {
      plugin.nodes.push(node.type)
    }
  }

  if (data.extra?.groupNodes) {
    for (const groupData of Object.values(data.extra.groupNodes) as { nodes?: ComfyNode[] }[]) {
      const groupNodes = groupData.nodes || []
      for (const node of groupNodes) {
        if (isVirtualNode(node.type)) {
          continue
        }
        
        const { githubUrl, pluginName } = resolvePluginInfo(node)
        
        if (!plugins.has(pluginName)) {
          plugins.set(pluginName, { githubUrl, count: 0, nodes: [] })
        }
        const plugin = plugins.get(pluginName)!
        plugin.count++
        if (!plugin.nodes.includes(node.type)) {
          plugin.nodes.push(node.type)
        }
      }
    }
  }

  return {
    totalNodes,
    virtualNodes,
    isApiFormat: false,
    totalLinks: Array.isArray(data?.links) ? data.links.length : 0,
    nodeTypes: Array.from(nodeTypes.entries()).map(([type, count]) => ({ type, count })),
    plugins: Array.from(plugins.entries()).map(([pluginName, info]) => ({
      githubUrl: info.githubUrl,
      name: pluginName,
      color: getPluginColor(info.githubUrl, pluginName),
      count: info.count,
      nodes: info.nodes
    }))
  }
}
