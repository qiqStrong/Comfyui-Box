/**
 * AboutHeader「检查更新」按钮测试
 *
 * 修复前该按钮直接 window.open(GitHub Releases)，绕过整套应用内更新流程。
 * 这些用例锁定：点击必须走 checkForUpdate，且三种结果都有正确反馈。
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import AboutHeader from '../AboutHeader'

const mocks = vi.hoisted(() => ({
  checkForUpdate: vi.fn(),
  isChecking: false,
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  markAsViewed: vi.fn(),
  windowOpen: vi.fn(),
}))

vi.mock('@/hooks/useAutoUpdateCheck', () => ({
  useAutoUpdateCheck: () => ({
    checkForUpdate: mocks.checkForUpdate,
    isChecking: mocks.isChecking,
    hasUpdate: false,
    updateInfo: null,
    hasViewed: false,
  }),
}))

vi.mock('@/stores/useAppUpdateStore', () => ({
  useAppUpdateStore: () => ({
    hasUpdate: false,
    hasViewed: false,
    markAsViewed: mocks.markAsViewed,
  }),
}))

vi.mock('@/utils/toast', () => ({
  toast: { success: mocks.toastSuccess, error: mocks.toastError },
}))

vi.mock('../UpdateDialog', () => ({ UpdateDialog: () => null }))

const checkButton = () =>
  screen.getByRole('button', { name: /检查更新|Check for Updates|正在检查|Checking for updates/ })

describe('AboutHeader 检查更新按钮', () => {
  beforeEach(() => {
    mocks.isChecking = false
    mocks.checkForUpdate.mockReset()
    mocks.toastSuccess.mockReset()
    mocks.toastError.mockReset()
    mocks.markAsViewed.mockReset()
    mocks.windowOpen.mockReset()
    vi.spyOn(window, 'open').mockImplementation(mocks.windowOpen)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('点击后调用应用内检查 API，不直接跳转 GitHub', async () => {
    mocks.checkForUpdate.mockResolvedValue({ status: 'update' })
    render(<AboutHeader version="V1.0.3" />)

    fireEvent.click(checkButton())

    await waitFor(() => expect(mocks.checkForUpdate).toHaveBeenCalledTimes(1))
    expect(mocks.windowOpen).not.toHaveBeenCalled()
  })

  it('已是最新时给出明确提示，不跳转 GitHub', async () => {
    mocks.checkForUpdate.mockResolvedValue({ status: 'uptodate' })
    render(<AboutHeader version="V1.0.3" />)

    fireEvent.click(checkButton())

    await waitFor(() => expect(mocks.toastSuccess).toHaveBeenCalledTimes(1))
    expect(mocks.toastError).not.toHaveBeenCalled()
    expect(mocks.windowOpen).not.toHaveBeenCalled()
  })

  it('检查失败时提示错误，GitHub 仅作为用户主动点击的兜底入口', async () => {
    mocks.checkForUpdate.mockResolvedValue({ status: 'error', error: '无法获取版本信息' })
    render(<AboutHeader version="V1.0.3" />)

    fireEvent.click(checkButton())

    await waitFor(() => expect(mocks.toastError).toHaveBeenCalledTimes(1))
    expect(mocks.windowOpen).not.toHaveBeenCalled()

    const options = mocks.toastError.mock.calls[0][1]
    expect(options?.action?.label).toBeTruthy()
    expect(typeof options?.action?.onClick).toBe('function')

    options.action.onClick()
    expect(mocks.windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('github.com/qiqStrong/Comfyui-Box'),
      '_blank',
      'noopener,noreferrer'
    )
  })

  it('检查中按钮禁用并显示检查中状态', () => {
    mocks.isChecking = true
    render(<AboutHeader version="V1.0.3" />)

    const button = checkButton() as HTMLButtonElement
    expect(button.disabled).toBe(true)
  })
})
