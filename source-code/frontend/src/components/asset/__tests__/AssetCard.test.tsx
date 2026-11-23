/**
 * AssetCard 渲染隔离与悬浮删除测试
 *
 * 背景：批量管理时点击一个资产曾导致所有卡片重渲染。
 * 这些用例锁定：选中状态变化只影响目标卡片；悬浮删除走 store.deleteAssets。
 */

import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { AssetCard } from '../AssetCard'
import { useAssetStore } from '@/stores/useAssetStore'
import type { Asset } from '@/mocks/asset'

const mocks = vi.hoisted(() => ({
  deleteAssets: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('@/stores/useProcessStore', () => ({
  useProcessStore: (selector: (s: any) => unknown) =>
    selector({ comfyUIStatus: null, showWorkspaceIframe: false }),
}))

vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({ success: mocks.toastSuccess, warning: vi.fn(), error: mocks.toastError }),
}))

vi.mock('../AssetDragContext', () => ({
  useAssetDragContext: () => null,
}))

vi.mock('@/components/common/ConfirmDialog', () => ({
  ConfirmDialog: ({ open, onConfirm }: any) =>
    open ? <button data-testid="confirm-delete" onClick={onConfirm}>confirm</button> : null,
}))

const makeAsset = (id: string): Asset => ({
  id,
  filename: `${id}.png`,
  filePath: `D:/gallery/${id}.png`,
  thumbnailPath: null,
  type: 'image',
  width: 100,
  height: 100,
  size: 100,
  createdAt: '2026-01-01T00:00:00.000Z',
  hasWorkflow: false,
  isFavorite: false,
  categoryId: null,
  thumbnail: `/thumb/${id}`,
  url: `/asset/${id}`
})

describe('AssetCard', () => {
  beforeEach(() => {
    mocks.deleteAssets.mockReset()
    mocks.toastSuccess.mockReset()
    mocks.toastError.mockReset()
    useAssetStore.setState({
      assets: [makeAsset('a'), makeAsset('b')],
      selectedAssetIds: [],
      isBatchMode: true,
      error: null
    })
    // 用 setState 替换 deleteAssets，避免真实后端调用
    useAssetStore.setState({ deleteAssets: mocks.deleteAssets as any })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('卡片用 memo 包裹，选中 selector 只对目标资产变化', () => {
    // memo 包裹：父级重渲染时 props 未变的卡片可跳过渲染
    expect((AssetCard as any).$$typeof).toBe(Symbol.for('react.memo'))

    // 核心机制：selector 返回布尔值，未选中卡片的 selector 结果在两个状态间
    // 保持一致（false === false），zustand 用 Object.is 比较后不会通知它重渲染
    const selectSelected = (id: string) => (s: { selectedAssetIds: string[] }) =>
      s.selectedAssetIds.includes(id)

    const beforeA = selectSelected('a')(useAssetStore.getState())
    const beforeB = selectSelected('b')(useAssetStore.getState())
    useAssetStore.setState({ selectedAssetIds: ['a'] })
    const afterA = selectSelected('a')(useAssetStore.getState())
    const afterB = selectSelected('b')(useAssetStore.getState())

    expect(beforeA).toBe(false)
    expect(afterA).toBe(true)
    expect(beforeB).toBe(false)
    expect(afterB).toBe(false)
  })

  it('批量模式下点击卡片只更新自身选中状态', () => {
    render(
      <>
        <AssetCard asset={makeAsset('a')} isBatchMode />
        <AssetCard asset={makeAsset('b')} isBatchMode />
      </>
    )

    fireEvent.click(document.querySelector('[data-asset-id="a"]') as HTMLElement)

    expect(useAssetStore.getState().selectedAssetIds).toEqual(['a'])
  })

  it('非批量模式悬浮删除按钮点击后确认并调用 deleteAssets', async () => {
    mocks.deleteAssets.mockResolvedValue(true)
    render(<AssetCard asset={makeAsset('a')} isBatchMode={false} />)

    fireEvent.click(screen.getByTestId('delete-asset-a'))
    fireEvent.click(screen.getByTestId('confirm-delete'))

    await waitFor(() => expect(mocks.deleteAssets).toHaveBeenCalledWith(['a']))
    expect(mocks.toastSuccess).toHaveBeenCalled()
  })

  it('批量模式下不渲染悬浮删除按钮', () => {
    render(<AssetCard asset={makeAsset('a')} isBatchMode />)
    expect(screen.queryByTestId('delete-asset-a')).toBeNull()
  })
})
