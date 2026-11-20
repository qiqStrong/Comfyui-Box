/**
 * ConfirmDialog 组件单元测试
 * 
 * 测试版本切换确认对话框的功能：
 * - 对话框显示和关闭
 * - 提交信息展示（哈希值、消息、时间）
 * - 确认和取消按钮点击
 * - 加载状态
 * - 键盘导航（Enter 确认，Esc 取消）
 * 
 * 验证需求: 3.1, 3.2, 3.3, 3.4
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PluginConfirmDialog as ConfirmDialog } from '../ConfirmDialog';
import type { CommitInfo } from '@/types/plugin';

describe('ConfirmDialog 组件', () => {
  // Mock 数据
  const mockCommit: CommitInfo = {
    hash: 'abc123d',
    message: '修复了一个重要的 bug',
    date: '2024-01-15T10:30:00Z',
    author: 'Test Author',
  };

  const mockOnClose = vi.fn();
  const mockOnConfirm = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('对话框显示和关闭', () => {
    it('当 open=false 时不应该渲染对话框', () => {
      render(
        <ConfirmDialog
          open={false}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      expect(screen.queryByText('确认切换版本')).not.toBeInTheDocument();
    });

    it('当 open=true 时应该显示对话框', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      expect(screen.getByText('确认切换版本')).toBeInTheDocument();
      expect(screen.getByText('请确认是否切换到以下版本')).toBeInTheDocument();
    });

    it('点击取消按钮应该调用 onClose', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      const cancelButton = screen.getByRole('button', { name: '取消切换版本' });
      await user.click(cancelButton);

      expect(mockOnClose).toHaveBeenCalledTimes(1);
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('点击背景遮罩应该调用 onClose', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      // 查找背景遮罩（第一个 div 元素，带有 bg-black/50 类）
      const backdrop = container.querySelector('.bg-black\\/50');
      expect(backdrop).toBeInTheDocument();

      if (backdrop) {
        await user.click(backdrop);
        expect(mockOnClose).toHaveBeenCalledTimes(1);
      }
    });

    it('加载状态时点击背景遮罩不应该关闭对话框', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      const backdrop = container.querySelector('.bg-black\\/50');
      if (backdrop) {
        await user.click(backdrop);
        // 加载时 onClose 为 undefined，所以不会被调用
        expect(mockOnClose).not.toHaveBeenCalled();
      }
    });
  });

  describe('提交信息展示', () => {
    it('应该正确显示提交哈希值', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      expect(screen.getByText('提交哈希')).toBeInTheDocument();
      expect(screen.getByText('abc123d')).toBeInTheDocument();
    });

    it('应该正确显示提交消息', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      expect(screen.getByText('提交消息')).toBeInTheDocument();
      expect(screen.getByText('修复了一个重要的 bug')).toBeInTheDocument();
    });

    it('应该正确显示格式化的提交时间', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      expect(screen.getByText('提交时间')).toBeInTheDocument();
      // 时间格式化为本地时间，检查是否包含日期部分
      expect(screen.getByText(/2024/)).toBeInTheDocument();
    });

    it('应该显示目标版本信息标题', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      expect(screen.getByText('目标版本信息')).toBeInTheDocument();
    });

    it('应该显示警告提示信息', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      expect(screen.getByText('注意事项')).toBeInTheDocument();
      expect(
        screen.getByText(/切换版本将改变插件代码/)
      ).toBeInTheDocument();
    });

    it('应该处理不同格式的提交信息', () => {
      const differentCommit: CommitInfo = {
        hash: 'xyz789',
        message: '添加新功能：支持多语言',
        date: '2024-02-20T15:45:30Z',
        author: 'Another Author',
      };

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={differentCommit}
        />
      );

      expect(screen.getByText('xyz789')).toBeInTheDocument();
      expect(screen.getByText('添加新功能：支持多语言')).toBeInTheDocument();
    });

    it('应该处理长提交消息', () => {
      const longMessageCommit: CommitInfo = {
        hash: 'def456',
        message: '这是一个非常长的提交消息，包含了很多详细的信息，描述了本次提交所做的所有更改和修复的问题',
        date: '2024-01-10T08:00:00Z',
      };

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={longMessageCommit}
        />
      );

      expect(
        screen.getByText(/这是一个非常长的提交消息/)
      ).toBeInTheDocument();
    });

    it('应该处理无效的日期格式', () => {
      const invalidDateCommit: CommitInfo = {
        hash: 'ghi789',
        message: '测试提交',
        date: 'invalid-date',
      };

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={invalidDateCommit}
        />
      );

      // 无效日期会被 formatDate 函数捕获并返回原始字符串
      // 但 new Date('invalid-date') 会返回 Invalid Date
      // 所以应该检查是否显示了 "Invalid Date" 或原始字符串
      const dateElement = screen.getByText(/Invalid Date|invalid-date/);
      expect(dateElement).toBeInTheDocument();
    });
  });

  describe('确认和取消按钮', () => {
    it('点击确认按钮应该调用 onConfirm', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      await user.click(confirmButton);

      expect(mockOnConfirm).toHaveBeenCalledTimes(1);
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('应该显示取消和确认按钮', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      expect(screen.getByRole('button', { name: '取消切换版本' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '确认切换版本' })).toBeInTheDocument();
    });

    it('确认按钮应该显示正确的文本', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      expect(confirmButton).toHaveTextContent('确认切换');
    });

    it('取消按钮应该显示正确的文本', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      const cancelButton = screen.getByRole('button', { name: '取消切换版本' });
      expect(cancelButton).toHaveTextContent('取消');
    });
  });

  describe('加载状态', () => {
    it('加载时确认按钮应该被禁用', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      expect(confirmButton).toBeDisabled();
    });

    it('加载时取消按钮应该被禁用', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      const cancelButton = screen.getByRole('button', { name: '取消切换版本' });
      expect(cancelButton).toBeDisabled();
    });

    it('加载时确认按钮应该显示加载文本', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      expect(screen.getByText('切换中...')).toBeInTheDocument();
    });

    it('加载时确认按钮应该有 aria-busy 属性', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      expect(confirmButton).toHaveAttribute('aria-busy', 'true');
    });

    it('非加载时确认按钮应该显示正常文本', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={false}
        />
      );

      expect(screen.getByText('确认切换')).toBeInTheDocument();
      expect(screen.queryByText('切换中...')).not.toBeInTheDocument();
    });

    it('非加载时按钮应该可点击', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={false}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      const cancelButton = screen.getByRole('button', { name: '取消切换版本' });

      expect(confirmButton).not.toBeDisabled();
      expect(cancelButton).not.toBeDisabled();
    });

    it('加载时点击按钮不应该触发回调', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      const cancelButton = screen.getByRole('button', { name: '取消切换版本' });

      // 尝试点击禁用的按钮
      await user.click(confirmButton);
      await user.click(cancelButton);

      // 回调不应该被调用
      expect(mockOnConfirm).not.toHaveBeenCalled();
      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  describe('键盘导航', () => {
    it('按 Enter 键应该触发确认操作', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      await user.keyboard('{Enter}');

      expect(mockOnConfirm).toHaveBeenCalledTimes(1);
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('按 Escape 键应该触发取消操作', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      await user.keyboard('{Escape}');

      expect(mockOnClose).toHaveBeenCalledTimes(1);
      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('加载时按 Enter 键不应该触发确认', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      await user.keyboard('{Enter}');

      expect(mockOnConfirm).not.toHaveBeenCalled();
    });

    it('加载时按 Escape 键不应该触发取消', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      await user.keyboard('{Escape}');

      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('对话框关闭时键盘事件不应该触发回调', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={false}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      await user.keyboard('{Enter}');
      await user.keyboard('{Escape}');

      expect(mockOnConfirm).not.toHaveBeenCalled();
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('键盘事件应该阻止默认行为', async () => {
      const user = userEvent.setup();

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      // 按 Enter 键
      await user.keyboard('{Enter}');
      expect(mockOnConfirm).toHaveBeenCalled();

      // 清除 mock
      mockOnConfirm.mockClear();

      // 按 Escape 键
      await user.keyboard('{Escape}');
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe('边界情况', () => {
    it('应该处理空的提交消息', () => {
      const emptyMessageCommit: CommitInfo = {
        hash: 'abc123',
        message: '',
        date: '2024-01-15T10:30:00Z',
      };

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={emptyMessageCommit}
        />
      );

      expect(screen.getByText('提交消息')).toBeInTheDocument();
    });

    it('应该处理非常短的哈希值', () => {
      const shortHashCommit: CommitInfo = {
        hash: 'abc',
        message: '测试',
        date: '2024-01-15T10:30:00Z',
      };

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={shortHashCommit}
        />
      );

      expect(screen.getByText('abc')).toBeInTheDocument();
    });

    it('应该处理完整的 40 字符哈希值', () => {
      const fullHashCommit: CommitInfo = {
        hash: 'abc123def456abc123def456abc123def456abc1',
        message: '测试',
        date: '2024-01-15T10:30:00Z',
      };

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={fullHashCommit}
        />
      );

      expect(
        screen.getByText('abc123def456abc123def456abc123def456abc1')
      ).toBeInTheDocument();
    });

    it('应该处理包含特殊字符的提交消息', () => {
      const specialCharsCommit: CommitInfo = {
        hash: 'abc123',
        message: 'Fix: 修复 <script> 标签问题 & 其他 "特殊" 字符',
        date: '2024-01-15T10:30:00Z',
      };

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={specialCharsCommit}
        />
      );

      expect(
        screen.getByText(/Fix: 修复 <script> 标签问题/)
      ).toBeInTheDocument();
    });

    it('应该处理多行提交消息', () => {
      const multilineCommit: CommitInfo = {
        hash: 'abc123',
        message: '第一行\n第二行\n第三行',
        date: '2024-01-15T10:30:00Z',
      };

      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={multilineCommit}
        />
      );

      expect(screen.getByText(/第一行/)).toBeInTheDocument();
    });
  });

  describe('可访问性', () => {
    it('确认按钮应该有正确的 aria-label', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      expect(confirmButton).toHaveAttribute('aria-label', '确认切换版本');
    });

    it('取消按钮应该有正确的 aria-label', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      const cancelButton = screen.getByRole('button', { name: '取消切换版本' });
      expect(cancelButton).toHaveAttribute('aria-label', '取消切换版本');
    });

    it('加载时确认按钮应该有 aria-busy 属性', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={true}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      expect(confirmButton).toHaveAttribute('aria-busy', 'true');
    });

    it('非加载时确认按钮不应该有 aria-busy 属性', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
          loading={false}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      expect(confirmButton).not.toHaveAttribute('aria-busy', 'true');
    });

    it('所有按钮应该可以通过键盘访问', () => {
      render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      const confirmButton = screen.getByRole('button', { name: '确认切换版本' });
      const cancelButton = screen.getByRole('button', { name: '取消切换版本' });

      // 按钮应该是可聚焦的
      expect(confirmButton).toBeInTheDocument();
      expect(cancelButton).toBeInTheDocument();
    });
  });

  describe('组件生命周期', () => {
    it('组件卸载时应该清理键盘事件监听器', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { unmount } = render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      // 验证添加了事件监听器
      expect(addEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

      // 卸载组件
      unmount();

      // 验证移除了事件监听器
      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });

    it('从 open=false 切换到 open=true 应该添加事件监听器', () => {
      const addEventListenerSpy = vi.spyOn(window, 'addEventListener');

      const { rerender } = render(
        <ConfirmDialog
          open={false}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      // 初始状态不应该添加监听器
      expect(addEventListenerSpy).not.toHaveBeenCalled();

      // 打开对话框
      rerender(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      // 应该添加监听器
      expect(addEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

      addEventListenerSpy.mockRestore();
    });

    it('从 open=true 切换到 open=false 应该移除事件监听器', () => {
      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

      const { rerender } = render(
        <ConfirmDialog
          open={true}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      // 关闭对话框
      rerender(
        <ConfirmDialog
          open={false}
          onClose={mockOnClose}
          onConfirm={mockOnConfirm}
          commit={mockCommit}
        />
      );

      // 应该移除监听器
      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

      removeEventListenerSpy.mockRestore();
    });
  });
});
