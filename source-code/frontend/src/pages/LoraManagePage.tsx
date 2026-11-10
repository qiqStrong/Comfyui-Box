/**
 * LoRA 管理页面
 */

import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Settings, Filter, Tag, Loader2, HardDrive, CloudDownload, ArrowDownAZ, ArrowUpZA, CheckSquare, Download } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { LoraSidebar } from '@/components/lora/LoraSidebar'
import { LoraCard } from '@/components/lora/LoraCard'
import { LoraSettingsModal } from '@/components/lora/LoraSettingsModal'
import { CivitaiPullModal, type ProgressInfo } from '@/components/lora/CivitaiPullModal'
import { LoraFolderManageDialog } from '@/components/lora/LoraFolderManageDialog'
import { LoraDragProvider, useLoraDragContext } from '@/components/lora/LoraDragContext'
import { LoraDragLayer } from '@/components/lora/LoraDragLayer'
import { LoraSelectionBox } from '@/components/lora/LoraSelectionBox'
import { LoraBatchToolbar } from '@/components/lora/LoraBatchToolbar'
import { bridgeService, type LoraModel } from '@/services/bridge'
import { cn } from '@/lib/utils'
import { ScopeBadge } from '@/components/common/ScopeBadge'

export default function LoraManagePage() {
  const { t } = useTranslation()
  const [models, setModels] = useState<LoraModel[]>([])
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFilters, setSelectedFilters] = useState<string[]>(['all'])
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [civitaiPullOpen, setCivitaiPullOpen] = useState(false)
  const [folderManageOpen, setFolderManageOpen] = useState(false)
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [pullingCivitai, setPullingCivitai] = useState(false)
  const [pullProgress, setPullProgress] = useState<ProgressInfo | null>(null)
  const [pullMinimized, setPullMinimized] = useState(false)
  const [pullStopping, setPullStopping] = useState(false)
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0)
  const [gridColumns, setGridColumns] = useState(2)
  const [previewShortEdge, setPreviewShortEdge] = useState(234)
  const [minimalList, setMinimalList] = useState(false)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [exporting, setExporting] = useState(false)
  
  const [isBatchMode, setIsBatchMode] = useState(false)
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([])
  const [isSelecting, setIsSelecting] = useState(false)
  const [selectionStart, setSelectionStart] = useState<{ x: number; y: number } | null>(null)
  const [selectionEnd, setSelectionEnd] = useState<{ x: number; y: number } | null>(null)
  const cardRefs = useRef<Map<string, HTMLElement>>(new Map())
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const loadDisplayConfig = async () => {
      try {
        const result = await bridgeService.loraGetConfig()
        if (result.success && result.config?.display) {
          setGridColumns(result.config.display.grid_columns ?? 2)
          setPreviewShortEdge(result.config.display.preview_short_edge ?? 234)
          setMinimalList(result.config.display.minimal_list ?? false)
          setSortOrder(result.config.display.sort_order ?? 'asc')
        }
      } catch (error) {
        console.error('加载显示配置失败:', error)
      }
    }
    loadDisplayConfig()
  }, [])

  useEffect(() => {
    (window as any).__loraGridColumnsUpdated = (columns: number) => {
      setGridColumns(columns)
    }
    return () => {
      delete (window as any).__loraGridColumnsUpdated
    }
  }, [])

  useEffect(() => {
    (window as any).__loraPreviewShortEdgeUpdated = (shortEdge: number) => {
      setPreviewShortEdge(shortEdge)
    }
    return () => {
      delete (window as any).__loraPreviewShortEdgeUpdated
    }
  }, [])

  useEffect(() => {
    (window as any).__loraMinimalListUpdated = (minimal: boolean) => {
      setMinimalList(minimal)
    }
    return () => {
      delete (window as any).__loraMinimalListUpdated
    }
  }, [])

  useEffect(() => {
    (window as any).__loraPullProgress = (progress: ProgressInfo) => {
      console.log('[LoraManagePage] 收到进度更新:', progress.stage, progress.current, '/', progress.total)
      setPullProgress(progress)
      
      if (progress.modelData) {
        console.log('[LoraManagePage] 更新模型数据:', progress.modelData.id, progress.modelData.name, 'isLocal:', progress.modelData.is_local, 'previewUrl:', progress.modelData.preview_url)
        setModels(prev => {
          const existingIndex = prev.findIndex(m => m.id === progress.modelData!.id)
          if (existingIndex >= 0) {
            const newModels = [...prev]
            newModels[existingIndex] = progress.modelData!
            console.log('[LoraManagePage] 模型已更新:', progress.modelData!.name, 'isLocal:', progress.modelData!.is_local)
            return newModels
          }
          console.log('[LoraManagePage] 模型未找到:', progress.modelData!.id)
          return prev
        })
      }
    }
    
    return () => {
      delete (window as any).__loraPullProgress
    }
  }, [])
  
  useEffect(() => {
    const checkPullStatus = async () => {
      try {
        const result = await bridgeService.loraGetPullStatus()
        if (result.pulling && result.progress) {
          setPullingCivitai(true)
          setPullProgress(result.progress)
          setCivitaiPullOpen(true)
          if (result.stopping) {
            setPullStopping(true)
          }
        }
      } catch (error) {
        console.error('检查拉取状态失败:', error)
      }
    }
    checkPullStatus()
  }, [])
  
  const gridColumnsStyle = useMemo(() => {
    return {
      gridTemplateColumns: `repeat(${gridColumns}, minmax(0, 1fr))`
    }
  }, [gridColumns])

  const allTags = useMemo(() => {
    const tagSet = new Set<string>()
    models.forEach(model => {
      if (model.tags && model.tags.length > 0) {
        model.tags.forEach(tag => tagSet.add(tag))
      }
    })
    return Array.from(tagSet).sort()
  }, [models])

  useEffect(() => {
    loadModels()
  }, [])

  const loadModels = async () => {
    setLoading(true)
    try {
      const result = await bridgeService.loraGetModels()
      if (result.success && result.models) {
        setModels(result.models)
      }
    } catch (error) {
      console.error('加载模型数据失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSyncModels = async () => {
    setSyncing(true)
    try {
      const result = await bridgeService.loraSyncModels()
      if (result.success) {
        const syncResult = result.result
        setToastMessage(
          t('lora.syncComplete', { added: syncResult?.added || 0, updated: syncResult?.updated || 0, removed: syncResult?.removed || 0 })
        )
        if (result.models) {
          setModels(result.models)
        } else {
          await loadModels()
        }
        setSidebarRefreshKey(prev => prev + 1)
      } else {
        setToastMessage(result.message || t('lora.syncFailed'))
      }
    } catch (error) {
      console.error('同步模型失败:', error)
      setToastMessage(t('lora.syncFailed'))
    } finally {
      setSyncing(false)
      setTimeout(() => setToastMessage(null), 3000)
    }
  }

  const handleFullPull = async () => {
    setPullingCivitai(true)
    setPullProgress(null)
    setPullMinimized(false)
    setPullStopping(false)
    try {
      const result = await bridgeService.loraPullFromCivitai(true)
      if (result.success) {
        setToastMessage(result.message || t('lora.fullPullComplete'))
        await loadModels()
      } else if (result.message === '已有拉取任务在进行中') {
        return
      } else {
        setToastMessage(result.message || t('lora.pullFailed'))
      }
    } catch (error) {
      console.error('全量拉取 Civitai 数据失败:', error)
      setToastMessage(t('lora.pullFailedMsg'))
      setPullProgress(null)
      setPullingCivitai(false)
    } finally {
      setPullMinimized(false)
      setPullStopping(false)
      setTimeout(() => setToastMessage(null), 3000)
    }
  }

  const handleIncrementalPull = async () => {
    setPullingCivitai(true)
    setPullProgress(null)
    setPullMinimized(false)
    setPullStopping(false)
    try {
      const result = await bridgeService.loraPullFromCivitai(false)
      if (result.success) {
        setToastMessage(result.message || t('lora.incrementalPullComplete'))
        await loadModels()
      } else if (result.message === '已有拉取任务在进行中') {
        return
      } else {
        setToastMessage(result.message || t('lora.pullFailedMsg'))
      }
    } catch (error) {
      console.error('增量拉取 Civitai 数据失败:', error)
      setToastMessage(t('lora.pullFailedMsg'))
      setPullProgress(null)
      setPullingCivitai(false)
    } finally {
      setPullMinimized(false)
      setPullStopping(false)
      setTimeout(() => setToastMessage(null), 3000)
    }
  }

  const handleClosePullModal = () => {
    setCivitaiPullOpen(false)
    setPullingCivitai(false)
    setPullProgress(null)
    setPullMinimized(false)
    setPullStopping(false)
  }

  const handleStopPull = async () => {
    setPullStopping(true)
    try {
      await bridgeService.loraStopPull()
      
      const checkStopped = async () => {
        const result = await bridgeService.loraGetPullStatus()
        if (!result.pulling) {
          setPullingCivitai(false)
          setPullProgress(null)
          setPullMinimized(false)
          setPullStopping(false)
          setCivitaiPullOpen(false)
          setToastMessage(t('lora.pullStopped'))
          setTimeout(() => setToastMessage(null), 3000)
          return true
        }
        return false
      }
      
      const pollInterval = setInterval(async () => {
        const stopped = await checkStopped()
        if (stopped) {
          clearInterval(pollInterval)
        }
      }, 500)
      
    } catch (error) {
      console.error('停止拉取失败:', error)
      setPullStopping(false)
    }
  }

  const handleToggleMinimize = () => {
    setPullMinimized(!pullMinimized)
  }

  const handleFilterClick = (filterId: string) => {
    if (filterId === 'all') {
      setSelectedFilters(['all'])
    } else {
      setSelectedFilters((prev) => {
        const newFilters = prev.filter((f) => f !== 'all')
        if (newFilters.includes(filterId)) {
          const result = newFilters.filter((f) => f !== filterId)
          return result.length === 0 ? ['all'] : result
        } else {
          return [...newFilters, filterId]
        }
      })
    }
  }

  const filteredModels = useMemo(() => {
    const result = models.filter((model) => {
      if (selectedFolder === 'uncategorized') {
        if (model.folder && model.folder !== '') {
          return false
        }
      } else if (selectedFolder && model.folder !== selectedFolder && model.category !== selectedFolder) {
        return false
      }
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return (
          model.name.toLowerCase().includes(query) ||
          (model.trigger_words && model.trigger_words.some((w) => w.toLowerCase().includes(query))) ||
          (model.tags && model.tags.some((t) => t.toLowerCase().includes(query)))
        )
      }
      if (!selectedFilters.includes('all') && selectedFilters.length > 0) {
        return model.tags && model.tags.some((t) => selectedFilters.includes(t))
      }
      return true
    })

    result.sort((a, b) => {
      const nameA = a.name.toLowerCase()
      const nameB = b.name.toLowerCase()
      if (sortOrder === 'asc') {
        return nameA.localeCompare(nameB)
      } else {
        return nameB.localeCompare(nameA)
      }
    })

    return result
  }, [models, selectedFolder, searchQuery, selectedFilters, sortOrder])

  const toggleModelSelection = useCallback((id: string) => {
    setSelectedModelIds(prev => {
      if (prev.includes(id)) {
        return prev.filter(modelId => modelId !== id)
      }
      return [...prev, id]
    })
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedModelIds([])
    setIsBatchMode(false)
  }, [])

  const handleBatchDelete = useCallback(async () => {
    if (selectedModelIds.length === 0) return
    
    for (const id of selectedModelIds) {
      try {
        await bridgeService.loraDeleteModel(id)
      } catch (error) {
        console.error('删除模型失败:', error)
      }
    }
    
    setModels(prev => prev.filter(m => !selectedModelIds.includes(m.id)))
    setSelectedModelIds([])
    setSidebarRefreshKey(prev => prev + 1)
    setToastMessage(t('lora.batchDeleteSuccess', { count: selectedModelIds.length }))
    setTimeout(() => setToastMessage(null), 3000)
  }, [selectedModelIds, t])

  const handleExportPreviews = useCallback(async () => {
    const modelIds = isBatchMode && selectedModelIds.length > 0
      ? selectedModelIds
      : filteredModels.map(m => m.id)

    if (modelIds.length === 0) return

    setExporting(true)
    try {
      const result = await bridgeService.loraBatchExportPreviews(modelIds)
      if (result.success) {
        setToastMessage(t('lora.exportPreviewsComplete', {
          exported: result.exported_count,
          skipped: result.skipped_count,
          failed: result.failed_count
        }))
        setTimeout(() => setToastMessage(null), 4000)
      } else {
        setToastMessage(t('lora.exportPreviewsFailed'))
        setTimeout(() => setToastMessage(null), 3000)
      }
    } catch (error) {
      console.error('导出预览图失败:', error)
      setToastMessage(t('lora.exportPreviewsFailed'))
      setTimeout(() => setToastMessage(null), 3000)
    } finally {
      setExporting(false)
    }
  }, [isBatchMode, selectedModelIds, filteredModels, t])

  const getIntersectingCardIds = useCallback((start: { x: number; y: number }, end: { x: number; y: number }) => {
    const selectionRect = {
      left: Math.min(start.x, end.x),
      right: Math.max(start.x, end.x),
      top: Math.min(start.y, end.y),
      bottom: Math.max(start.y, end.y)
    }

    const intersectingIds: string[] = []
    cardRefs.current.forEach((cardEl, modelId) => {
      const cardRect = cardEl.getBoundingClientRect()
      if (
        cardRect.left < selectionRect.right &&
        cardRect.right > selectionRect.left &&
        cardRect.top < selectionRect.bottom &&
        cardRect.bottom > selectionRect.top
      ) {
        intersectingIds.push(modelId)
      }
    })
    return intersectingIds
  }, [])

  const handleSelectionMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return
    if ((e.target as HTMLElement).closest('[data-lora-card]')) return
    if ((e.target as HTMLElement).closest('button')) return
    if ((e.target as HTMLElement).closest('input')) return
    if ((e.target as HTMLElement).closest('a')) return

    setIsSelecting(true)
    setSelectionStart({ x: e.clientX, y: e.clientY })
    setSelectionEnd({ x: e.clientX, y: e.clientY })
  }, [])

  const handleSelectionMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isSelecting) return
    setSelectionEnd({ x: e.clientX, y: e.clientY })

    if (selectionStart) {
      const intersectingIds = getIntersectingCardIds(selectionStart, { x: e.clientX, y: e.clientY })
      if (intersectingIds.length > 0 && !isBatchMode) {
        setIsBatchMode(true)
      }
      
      setSelectedModelIds(prev => {
        const newIds = new Set(prev)
        intersectingIds.forEach(id => newIds.add(id))
        return Array.from(newIds)
      })
    }
  }, [isSelecting, selectionStart, getIntersectingCardIds, isBatchMode])

  const handleSelectionMouseUp = useCallback(() => {
    setIsSelecting(false)
    setSelectionStart(null)
    setSelectionEnd(null)
  }, [])

  const handleDropToFolder = useCallback(async (folderId: string, modelIds: string[]) => {
    try {
      const targetFolderId = folderId === 'uncategorized' ? '' : folderId
      const result = await bridgeService.loraBatchUpdateFolder(modelIds, targetFolderId)
      if (result.success) {
        await loadModels()
        setSidebarRefreshKey(prev => prev + 1)
        setToastMessage(t('lora.batchMoveSuccess', { count: result.updated_count }))
        setTimeout(() => setToastMessage(null), 3000)
      }
    } catch (error) {
      console.error('批量移动失败:', error)
    }
  }, [t])

  const minimalListContainerRef = useRef<HTMLDivElement>(null)
  const [cardsPerRow, setCardsPerRow] = useState(1)

  useEffect(() => {
    const calculateCardsPerRow = () => {
      if (!minimalListContainerRef.current) return
      const containerWidth = minimalListContainerRef.current.clientWidth
      const cardWidth = previewShortEdge
      const gap = 20
      const cards = Math.floor((containerWidth + gap) / (cardWidth + gap))
      console.log('[LoraManagePage] 列数计算:', { containerWidth, cardWidth, gap, cards: Math.max(1, cards) })
      setCardsPerRow(Math.max(1, cards))
    }

    const timer = setTimeout(calculateCardsPerRow, 100)
    window.addEventListener('resize', calculateCardsPerRow)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('resize', calculateCardsPerRow)
    }
  }, [previewShortEdge, minimalList, filteredModels.length])

  const minimalListContainerStyle = useMemo(() => {
    const cardWidth = previewShortEdge
    const gap = 20
    const innerWidth = cardWidth * cardsPerRow + gap * (cardsPerRow - 1)
    return {
      display: 'flex' as const,
      flexWrap: 'wrap' as const,
      gap: `${gap}px`,
      justifyContent: 'flex-start' as const,
      width: `${innerWidth}px`,
    }
  }, [previewShortEdge, cardsPerRow])

  const handleCopyTriggerWord = (word: string) => {
    navigator.clipboard.writeText(word).then(() => {
      setToastMessage(t('lora.copied', { word }))
      setTimeout(() => setToastMessage(null), 2000)
    })
  }

  const formatSize = (sizeKb: number): string => {
    if (sizeKb >= 1024 * 1024) {
      return `${(sizeKb / (1024 * 1024)).toFixed(2)} GB`
    } else if (sizeKb >= 1024) {
      return `${(sizeKb / 1024).toFixed(2)} MB`
    } else {
      return `${sizeKb.toFixed(2)} KB`
    }
  }

  const totalSize = models.reduce((sum, m) => sum + (m.size_kb || 0), 0)

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background font-sans text-foreground">
      <header className="z-20 shrink-0 border-b border-border/60 bg-surface p-4 pb-3 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-4">
          <div className="relative max-w-xl flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder={t("common.placeholder.searchByNameTag")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9"
            />
          </div>
          <div className="flex items-center gap-3">
            <ScopeBadge category="lora" />
            <Button 
              variant="outline" 
              className="flex items-center gap-0 px-3"
              onClick={async () => {
                const newOrder = sortOrder === 'asc' ? 'desc' : 'asc'
                setSortOrder(newOrder)
                try {
                  await bridgeService.loraUpdateConfig({
                    display: { sort_order: newOrder }
                  })
                } catch (error) {
                  console.error('保存排序设置失败:', error)
                }
              }}
              title={sortOrder === 'asc' ? t('lora.sortAsc') : t('lora.sortDesc')}
            >
              {sortOrder === 'asc' ? (
                <ArrowDownAZ className="size-4" />
              ) : (
                <ArrowUpZA className="size-4" />
              )}
            </Button>
            <Button 
              variant="outline" 
              className="flex items-center gap-2"
              onClick={handleSyncModels}
              disabled={syncing}
            >
              {syncing ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <HardDrive className="size-4" />
              )}
              {t('lora.syncLocal')}
            </Button>
            <Button 
              onClick={() => setCivitaiPullOpen(true)} 
              disabled={pullingCivitai}
              variant="outline"
              className="flex items-center gap-2"
            >
              {pullingCivitai ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <CloudDownload className="size-4" />
              )}
              {t('lora.pullCivitai')}
            </Button>
            <Button
              variant="outline"
              className="flex items-center gap-2"
              onClick={handleExportPreviews}
              disabled={exporting || filteredModels.length === 0}
            >
              {exporting ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Download className="size-4" />
              )}
              {t('lora.exportPreviews')}
            </Button>
            <Button onClick={() => setSettingsOpen(true)} className="flex items-center gap-2">
              <Settings className="size-4" /> {t('common.settings')}
            </Button>
            <Button
              variant={isBatchMode ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setIsBatchMode(!isBatchMode)
                if (isBatchMode) {
                  setSelectedModelIds([])
                }
              }}
              className="flex items-center gap-2"
            >
              <CheckSquare className="size-4" />
              {isBatchMode ? t('lora.batch.done') : t('lora.batch.mode')}
            </Button>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex shrink-0 items-center gap-1 text-[13px] font-medium text-muted-foreground">
              <Filter className="size-3 opacity-70" /> {t('lora.quickFilter')}:
            </span>
            <span
              onClick={() => handleFilterClick('all')}
              className={cn(
                'flex items-center px-3 py-1 rounded-md text-xs cursor-pointer whitespace-nowrap transition-colors',
                selectedFilters.includes('all')
                  ? 'bg-primary/10 text-primary border border-primary/30'
                  : 'bg-muted/50 hover:bg-muted'
              )}
            >
              <Filter className="mr-1.5 size-2.5 opacity-70" />
              {t('common.label.all')}
            </span>
            {allTags.map((tag) => (
              <span
                key={tag}
                onClick={() => handleFilterClick(tag)}
                className={cn(
                  'flex items-center px-3 py-1 rounded-md text-xs cursor-pointer whitespace-nowrap transition-colors',
                  selectedFilters.includes(tag)
                    ? 'bg-primary/10 text-primary border border-primary/30'
                    : 'bg-muted/50 hover:bg-muted'
                )}
              >
                <Tag className="mr-1.5 size-2.5 opacity-70" />
                {tag}
              </span>
            ))}
          </div>
          <div className="text-xs text-muted-foreground">
            {t('lora.totalModels', { count: models.length, size: formatSize(totalSize) })}
          </div>
        </div>
      </header>

      <LoraDragProvider onDrop={handleDropToFolder}>
        <LoraManageMain
          selectedFolder={selectedFolder}
          setSelectedFolder={setSelectedFolder}
          sidebarRefreshKey={sidebarRefreshKey}
          loading={loading}
          filteredModels={filteredModels}
          minimalList={minimalList}
          minimalListContainerRef={minimalListContainerRef}
          minimalListContainerStyle={minimalListContainerStyle}
          gridColumnsStyle={gridColumnsStyle}
          previewShortEdge={previewShortEdge}
          handleCopyTriggerWord={handleCopyTriggerWord}
          setModels={setModels}
          setSidebarRefreshKey={setSidebarRefreshKey}
          setToastMessage={setToastMessage}
          t={t}
          isBatchMode={isBatchMode}
          selectedModelIds={selectedModelIds}
          toggleModelSelection={toggleModelSelection}
          cardRefs={cardRefs}
          handleSelectionMouseDown={handleSelectionMouseDown}
          handleSelectionMouseMove={handleSelectionMouseMove}
          handleSelectionMouseUp={handleSelectionMouseUp}
          scrollContainerRef={scrollContainerRef}
          isSelecting={isSelecting}
          selectionStart={selectionStart}
          selectionEnd={selectionEnd}
          onOpenFolderManage={() => setFolderManageOpen(true)}
        />
      </LoraDragProvider>

      <LoraSettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      
      <LoraFolderManageDialog
        open={folderManageOpen}
        onOpenChange={setFolderManageOpen}
        onRefresh={() => setSidebarRefreshKey(prev => prev + 1)}
      />
      
      <CivitaiPullModal
        open={civitaiPullOpen}
        onClose={handleClosePullModal}
        onFullPull={handleFullPull}
        onIncrementalPull={handleIncrementalPull}
        onStop={handleStopPull}
        loading={pullingCivitai}
        progress={pullProgress}
        minimized={pullMinimized}
        stopping={pullStopping}
        onToggleMinimize={handleToggleMinimize}
      />

      {toastMessage && (
        <div className="animate-in fade-in slide-in-from-bottom-2 fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-full border border-border bg-surface px-4 py-2 text-sm text-content-primary shadow-xl">
          {toastMessage}
        </div>
      )}
      
      <LoraBatchToolbar
        selectedCount={selectedModelIds.length}
        totalCount={filteredModels.length}
        onClearSelection={clearSelection}
        onBatchDelete={handleBatchDelete}
      />
    </div>
  )
}

interface LoraManageMainProps {
  selectedFolder: string | null
  setSelectedFolder: (folder: string | null) => void
  sidebarRefreshKey: number
  loading: boolean
  filteredModels: LoraModel[]
  minimalList: boolean
  minimalListContainerRef: React.RefObject<HTMLDivElement | null>
  minimalListContainerStyle: React.CSSProperties
  gridColumnsStyle: React.CSSProperties
  previewShortEdge: number
  handleCopyTriggerWord: (word: string) => void
  setModels: React.Dispatch<React.SetStateAction<LoraModel[]>>
  setSidebarRefreshKey: React.Dispatch<React.SetStateAction<number>>
  setToastMessage: React.Dispatch<React.SetStateAction<string | null>>
  t: (key: string, options?: Record<string, unknown>) => string
  isBatchMode: boolean
  selectedModelIds: string[]
  toggleModelSelection: (id: string) => void
  cardRefs: React.MutableRefObject<Map<string, HTMLElement>>
  handleSelectionMouseDown: (e: React.MouseEvent) => void
  handleSelectionMouseMove: (e: React.MouseEvent) => void
  handleSelectionMouseUp: () => void
  scrollContainerRef: React.RefObject<HTMLDivElement | null>
  isSelecting: boolean
  selectionStart: { x: number; y: number } | null
  selectionEnd: { x: number; y: number } | null
  onOpenFolderManage: () => void
}

function LoraManageMain({
  selectedFolder,
  setSelectedFolder,
  sidebarRefreshKey,
  loading,
  filteredModels,
  minimalList,
  minimalListContainerRef,
  minimalListContainerStyle,
  gridColumnsStyle,
  previewShortEdge,
  handleCopyTriggerWord,
  setModels,
  setSidebarRefreshKey,
  setToastMessage,
  t,
  isBatchMode,
  selectedModelIds,
  toggleModelSelection,
  cardRefs,
  handleSelectionMouseDown,
  handleSelectionMouseMove,
  handleSelectionMouseUp,
  scrollContainerRef,
  isSelecting,
  selectionStart,
  selectionEnd,
  onOpenFolderManage,
}: LoraManageMainProps) {
  const { dropTargetFolderId, setDropTargetFolderId, startDrag, updatePosition, endDrag, isDragging } = useLoraDragContext()
  
  const forceCollapsed = isDragging || isSelecting

  const handleDragStart = useCallback((modelId: string, clientX: number, clientY: number) => {
    startDrag(modelId, selectedModelIds, clientX, clientY)

    const handleMouseMove = (e: MouseEvent) => {
      updatePosition(e.clientX, e.clientY)

      const target = document.elementFromPoint(e.clientX, e.clientY)
      const folderItem = target?.closest('[data-folder-id]')

      if (folderItem) {
        const folderId = folderItem.getAttribute('data-folder-id')
        setDropTargetFolderId(folderId)
      } else {
        setDropTargetFolderId(null)
      }
    }

    const handleMouseUp = () => {
      endDrag()
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [startDrag, selectedModelIds, updatePosition, setDropTargetFolderId, endDrag])

  return (
    <>
      <main className="flex flex-1 overflow-hidden">
        <LoraSidebar
          selectedFolder={selectedFolder}
          onSelectFolder={setSelectedFolder}
          refreshKey={sidebarRefreshKey}
          dropTargetFolderId={dropTargetFolderId}
          onOpenFolderManage={onOpenFolderManage}
        />

        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto p-5"
          onMouseDown={handleSelectionMouseDown}
          onMouseMove={handleSelectionMouseMove}
          onMouseUp={handleSelectionMouseUp}
          onMouseLeave={handleSelectionMouseUp}
        >
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="size-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredModels.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <HardDrive className="mb-4 size-12 opacity-50" />
              <p className="text-lg font-medium">{t("lora.noModelData")}</p>
            </div>
          ) : minimalList ? (
            <div ref={minimalListContainerRef} className="flex w-full justify-center">
              <div style={minimalListContainerStyle}>
                {filteredModels.map((model) => (
                  <LoraCard
                    key={model.id}
                    ref={(el) => {
                      if (el) cardRefs.current.set(model.id, el)
                    }}
                    id={model.id}
                    name={model.name}
                    triggerWords={model.trigger_words || []}
                    tags={model.tags || []}
                    defaultWeight={model.default_weight || ""}
                    recommendedSampler={model.recommended_sampler}
                    civitaiUrl={model.civitai_url}
                    notes={model.notes}
                    sizeKb={model.size_kb}
                    previewUrl={model.preview_url}
                    isLocal={model.is_local}
                    previewBlurred={model.preview_blurred}
                    previewShortEdge={previewShortEdge}
                    onCopyTriggerWord={handleCopyTriggerWord}
                    onRename={(modelId, newName) => {
                      setModels(prev => prev.map(m => 
                        m.id === modelId ? { ...m, name: newName } : m
                      ))
                    }}
                    onTagsChange={(modelId, newTags) => {
                      setModels(prev => prev.map(m => 
                        m.id === modelId ? { ...m, tags: newTags } : m
                      ))
                    }}
                    onNotesChange={(modelId, newNotes) => {
                      setModels(prev => prev.map(m => 
                        m.id === modelId ? { ...m, notes: newNotes } : m
                      ))
                    }}
                    onPreviewBlurredChange={(modelId, blurred) => {
                      setModels(prev => prev.map(m => 
                        m.id === modelId ? { ...m, preview_blurred: blurred } : m
                      ))
                    }}
                    onDelete={(modelId) => {
                      setModels(prev => prev.filter(m => m.id !== modelId))
                      setSidebarRefreshKey(prev => prev + 1)
                      setToastMessage(t('lora.deleteModel.success'))
                      setTimeout(() => setToastMessage(null), 3000)
                    }}
                    variant="minimal"
                    isBatchMode={isBatchMode}
                    isSelected={selectedModelIds.includes(model.id)}
                    onSelect={toggleModelSelection}
                    onDragStart={handleDragStart}
                    forceCollapsed={forceCollapsed}
                  />
                ))}
              </div>
            </div>
          ) : (
            <div className="grid items-start gap-5" style={gridColumnsStyle}>
              {filteredModels.map((model) => (
                <LoraCard
                  key={model.id}
                  ref={(el) => {
                    if (el) cardRefs.current.set(model.id, el)
                  }}
                  id={model.id}
                  name={model.name}
                  triggerWords={model.trigger_words || []}
                  tags={model.tags || []}
                  defaultWeight={model.default_weight || ""}
                  civitaiUrl={model.civitai_url}
                  notes={model.notes}
                  sizeKb={model.size_kb}
                  previewUrl={model.preview_url}
                  isLocal={model.is_local}
                  previewBlurred={model.preview_blurred}
                  previewShortEdge={previewShortEdge}
                  onCopyTriggerWord={handleCopyTriggerWord}
                  onRename={(modelId, newName) => {
                    setModels(prev => prev.map(m => 
                      m.id === modelId ? { ...m, name: newName } : m
                    ))
                  }}
                  onTagsChange={(modelId, newTags) => {
                    setModels(prev => prev.map(m => 
                      m.id === modelId ? { ...m, tags: newTags } : m
                    ))
                  }}
                  onNotesChange={(modelId, newNotes) => {
                    setModels(prev => prev.map(m => 
                      m.id === modelId ? { ...m, notes: newNotes } : m
                    ))
                  }}
                  onPreviewBlurredChange={(modelId, blurred) => {
                    setModels(prev => prev.map(m => 
                      m.id === modelId ? { ...m, preview_blurred: blurred } : m
                    ))
                  }}
                  onDelete={(modelId) => {
                    setModels(prev => prev.filter(m => m.id !== modelId))
                    setSidebarRefreshKey(prev => prev + 1)
                    setToastMessage(t('lora.deleteModel.success'))
                    setTimeout(() => setToastMessage(null), 3000)
                  }}
                  isBatchMode={isBatchMode}
                  isSelected={selectedModelIds.includes(model.id)}
                  onSelect={toggleModelSelection}
                  onDragStart={handleDragStart}
                  forceCollapsed={forceCollapsed}
                />
              ))}
            </div>
          )}
          {minimalList && (
            <div style={{ height: Math.round(previewShortEdge * 4 / 3 / 2) + 10 }} />
          )}
        </div>
      </main>
      
      <LoraDragLayer
        getCardRefs={() => cardRefs.current}
        previewShortEdge={previewShortEdge}
        minimalList={minimalList}
      />
      
      {isSelecting && selectionStart && selectionEnd && (
        <LoraSelectionBox startPoint={selectionStart} endPoint={selectionEnd} />
      )}
    </>
  )
}
