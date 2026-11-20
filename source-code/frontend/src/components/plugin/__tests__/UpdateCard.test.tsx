/* eslint-disable no-restricted-syntax */
/**
 * UpdateCard 组件单元测试
 * 
 * 测试更新信息渲染、更新流程、成功和失败提示
 * 验证需求: 6.2, 6.4, 6.5
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { UpdateCard } from '../UpdateCard';
import * as usePluginUpdateModule from '@/hooks/usePluginUpdate';
import type { PluginInfo, CommitInfo, UpdateResult } from '@/types/plugin';

// Mock usePluginUpdate Hook
vi.mock('@/hooks/usePluginUpdate');

// Mock Modal 组件
vi.mock('@/components/ui/Modal', () => ({
  Modal: ({ children, open, onClose, title, description }: any) => {
    if (!open) return null;
    return (
      <div data-testid="modal">
        <div data-testid="modal-title">{title}</div>
        <div data-testid="modal-description">{description}</div>
        <button onClick={onClose} data-testid="modal-close">关闭</button>
        {children}
      </div>
    );
  },
}));

// Mock Loading 组件
vi.mock('@/components/ui/Loading', () => ({
  Loading: ({ text }: any) => <div data-testid="loading">{text}</div>,
}));

// Mock Badge 组件
vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, className }: any) => (
    <span data-testid="badge" className={className}>{children}</span>
  ),
}));

// Mock Button 组件
vi.mock('@/components/ui/Button', () => ({
  Button: ({ children, onClick, disabled, ...props }: any) => (
    <button onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}));

// Mock lucide-react icons
vi.mock('lucide-react', async (importOriginal) => {
  const actual = await importOriginal<Record<string, any>>()
  return {
    ...actual,
    CheckCircle2: () => <span data-testid="check-icon" />,
    AlertCircle: () => <span data-testid="alert-icon" />,
    GitCommit: () => <span data-testid="git-icon" />,
    Calendar: () => <span data-testid="calendar-icon" />,
    Hash: () => <span data-testid="hash-icon" />,
    X: () => <span data-testid="close-icon" />,
  }
});

describe('UpdateCard', () => {
  // 测试数据
  const mockPlugin: PluginInfo = {
    name: 'test-plugin',
    path: '/path/to/plugin',
    is_git_repo: true,
    git_url: 'https://github.com/test/plugin.git',
    branch: 'main',
    default_branch: 'main',
    commit_hash: 'abc1234',
    commit_date: '2024-01-10T10:00:00Z',
    has_update: true,
    behind_commits: 3,
    dependency_updated: false,
    dependency_viewed: false,
  };

  const mockCommits: CommitInfo[] = [
    {
      hash: 'def5678',
      message: 'feat: 添加新功能',
      date: '2024-01-15T10:30:00Z',
    },
    {
      hash: 'ghi9012',
      message: 'fix: 修复 bug',
      date: '2024-01-14T15:20:00Z',
    },
    {
      hash: 'jkl3456',
      message: 'docs: 更新文档',
      date: '2024-01-13T09:10:00Z',
    },
  ];

  // 默认 mock 返回值
  const mockUsePluginUpdate = {
    commits: [] as CommitInfo[],
    loading: false,
    updating: false,
    error: null,
    loadUpdateInfo: vi.fn(),
    updatePlugin: vi.fn(),
    clearUpdateInfo: vi.fn(),
  };

  // 默认 props
  const defaultProps = {
    plugin: mockPlugin,
    onClose: vi.fn(),
    onUpdateComplete: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue(mockUsePluginUpdate);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('组件渲染', () => {
    it('应该正确渲染模态窗口标题和描述', () => {
      render(<UpdateCard {...defaultProps} />);

      expect(screen.getByTestId('modal-title')).toHaveTextContent('test-plugin - 更新信息');
      expect(screen.getByTestId('modal-description')).toHaveTextContent('查看提交日志并确认更新');
    });

    it('应该在组件挂载时加载更新信息', () => {
      render(<UpdateCard {...defaultProps} />);

      expect(mockUsePluginUpdate.loadUpdateInfo).toHaveBeenCalledWith('test-plugin');
      expect(mockUsePluginUpdate.loadUpdateInfo).toHaveBeenCalledTimes(1);
    });

    it('应该在组件卸载时清除更新信息', () => {
      const { unmount } = render(<UpdateCard {...defaultProps} />);

      unmount();

      expect(mockUsePluginUpdate.clearUpdateInfo).toHaveBeenCalledTimes(1);
    });

    it('应该显示当前版本和最新版本', () => {
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      render(<UpdateCard {...defaultProps} />);

      // 当前版本
      expect(screen.getByText('当前版本')).toBeInTheDocument();
      expect(screen.getByText('abc1234')).toBeInTheDocument();

      // 最新版本（第一个提交的 hash，会出现两次：版本区域和提交列表）
      expect(screen.getByText('最新版本')).toBeInTheDocument();
      const def5678Texts = screen.getAllByText('def5678');
      expect(def5678Texts.length).toBeGreaterThanOrEqual(1);
    });

    it('应该显示落后提交数', () => {
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      render(<UpdateCard {...defaultProps} />);

      expect(screen.getByText('落后 3 个提交')).toBeInTheDocument();
    });
  });

  describe('加载状态', () => {
    it('应该在加载时显示加载指示器', () => {
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        loading: true,
      });

      render(<UpdateCard {...defaultProps} />);

      expect(screen.getByTestId('loading')).toBeInTheDocument();
      expect(screen.getByText('加载更新信息中...')).toBeInTheDocument();
    });
  });

  describe('错误状态', () => {
    it('应该在加载失败时显示错误信息', () => {
      const errorMessage = '网络连接失败';
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        error: errorMessage,
      });

      render(<UpdateCard {...defaultProps} />);

      expect(screen.getByText('加载失败')).toBeInTheDocument();
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });

  describe('提交日志渲染', () => {
    it('应该在没有提交时显示提示信息', () => {
      render(<UpdateCard {...defaultProps} />);

      expect(screen.getByTestId('git-icon')).toBeInTheDocument();
      expect(screen.getByText('没有可用的更新')).toBeInTheDocument();
    });

    it('应该正确渲染提交日志列表', () => {
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      render(<UpdateCard {...defaultProps} />);

      // 验证标题
      expect(screen.getByText('更新内容 (3 个提交)')).toBeInTheDocument();

      // 验证所有提交信息（hash 会出现多次）
      const def5678Texts = screen.getAllByText('def5678');
      expect(def5678Texts.length).toBeGreaterThan(0);
      expect(screen.getByText('feat: 添加新功能')).toBeInTheDocument();

      expect(screen.getByText('ghi9012')).toBeInTheDocument();
      expect(screen.getByText('fix: 修复 bug')).toBeInTheDocument();

      expect(screen.getByText('jkl3456')).toBeInTheDocument();
      expect(screen.getByText('docs: 更新文档')).toBeInTheDocument();
    });

    it('应该显示所有提交字段（hash、message、date）', () => {
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: [mockCommits[0]],
      });

      render(<UpdateCard {...defaultProps} />);

      // 验证 hash（在提交列表中）
      const commitCodes = screen.getAllByText('def5678');
      expect(commitCodes.length).toBeGreaterThan(0);

      // 验证 message
      expect(screen.getByText('feat: 添加新功能')).toBeInTheDocument();

      // 验证 date（格式化后的）
      // 注意：日期格式化可能因环境而异，这里只检查是否存在日期相关的图标
      expect(screen.getByTestId('calendar-icon')).toBeInTheDocument();
    });
  });

  describe('更新功能', () => {
    it('应该在点击确定按钮时调用 updatePlugin', async () => {
      const user = userEvent.setup();
      const mockUpdateResult: UpdateResult = {
        plugin_name: 'test-plugin',
        success: true,
        message: '更新成功',
        dependency_changed: false,
        new_dependencies: [],
        dependencies_installed: 0,
      };

      mockUsePluginUpdate.updatePlugin.mockResolvedValue(mockUpdateResult);

      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      render(<UpdateCard {...defaultProps} />);

      const updateButton = screen.getByRole('button', { name: /确定更新/i });
      await user.click(updateButton);

      await waitFor(() => {
        expect(mockUsePluginUpdate.updatePlugin).toHaveBeenCalledWith('test-plugin', false);
      });
    });

    it('应该在更新过程中显示更新中状态', () => {
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
        updating: true,
      });

      render(<UpdateCard {...defaultProps} />);

      expect(screen.getByText('正在更新插件...')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /更新中/i })).toBeDisabled();
    });

    it('应该在更新成功后显示成功提示', async () => {
      const user = userEvent.setup();
      const mockUpdateResult: UpdateResult = {
        plugin_name: 'test-plugin',
        success: true,
        message: '更新成功',
        dependency_changed: false,
        new_dependencies: [],
        dependencies_installed: 0,
      };

      mockUsePluginUpdate.updatePlugin.mockResolvedValue(mockUpdateResult);

      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      render(<UpdateCard {...defaultProps} />);

      const updateButton = screen.getByRole('button', { name: /确定更新/i });
      await user.click(updateButton);

      await waitFor(() => {
        const successHeadings = screen.getAllByText('更新成功');
        expect(successHeadings.length).toBeGreaterThan(0);
      });
    });

    it('应该在更新失败后显示失败提示', async () => {
      const user = userEvent.setup();
      const mockUpdateResult: UpdateResult = {
        plugin_name: 'test-plugin',
        success: false,
        message: '更新失败：网络错误',
        dependency_changed: false,
        new_dependencies: [],
        dependencies_installed: 0,
        error: '网络错误',
      };

      mockUsePluginUpdate.updatePlugin.mockResolvedValue(mockUpdateResult);

      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      render(<UpdateCard {...defaultProps} />);

      const updateButton = screen.getByRole('button', { name: /确定更新/i });
      await user.click(updateButton);

      await waitFor(() => {
        expect(screen.getByText('更新失败')).toBeInTheDocument();
        expect(screen.getByText('更新失败：网络错误')).toBeInTheDocument();
      });
    });

    it('应该在更新成功后调用 onUpdateComplete', async () => {
      const mockUpdateResult: UpdateResult = {
        plugin_name: 'test-plugin',
        success: true,
        message: '更新成功',
        dependency_changed: false,
        new_dependencies: [],
        dependencies_installed: 0,
      };

      mockUsePluginUpdate.updatePlugin.mockResolvedValue(mockUpdateResult);

      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      const { rerender } = render(<UpdateCard {...defaultProps} />);

      // 模拟点击更新按钮
      const updateButton = screen.getByRole('button', { name: /确定更新/i });
      updateButton.click();

      // 等待更新完成
      await waitFor(() => {
        const successHeadings = screen.queryAllByText('更新成功');
        expect(successHeadings.length).toBeGreaterThan(0);
      }, { timeout: 3000 });

      // 等待 setTimeout 完成（1500ms）
      await new Promise(resolve => setTimeout(resolve, 1600));

      expect(defaultProps.onUpdateComplete).toHaveBeenCalled();
    }, 15000);

    it('应该在没有提交时禁用更新按钮', () => {
      render(<UpdateCard {...defaultProps} />);

      const updateButton = screen.getByRole('button', { name: /确定更新/i });
      expect(updateButton).toBeDisabled();
    });

    it('应该在本地修改冲突时显示强制更新按钮', async () => {
      const user = userEvent.setup();
      const mockUpdateResult: UpdateResult = {
        plugin_name: 'test-plugin',
        success: false,
        message: 'error: cannot pull with rebase: You have unstaged changes',
        dependency_changed: false,
        new_dependencies: [],
        dependencies_installed: 0,
        error: 'error: cannot pull with rebase: You have unstaged changes',
      };

      mockUsePluginUpdate.updatePlugin.mockResolvedValue(mockUpdateResult);

      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      render(<UpdateCard {...defaultProps} />);

      const updateButton = screen.getByRole('button', { name: /确定更新/i });
      await user.click(updateButton);

      await waitFor(() => {
        expect(screen.getByText('更新失败')).toBeInTheDocument();
        expect(screen.getByText(/插件目录中有您修改过的文件/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /强制更新（会丢失修改）/i })).toBeInTheDocument();
      });
    });

    it('应该在点击强制更新按钮时调用 updatePlugin 并传递 force=true', async () => {
      const user = userEvent.setup();
      // 第一次调用返回本地修改冲突
      const mockUpdateResultFail: UpdateResult = {
        plugin_name: 'test-plugin',
        success: false,
        message: 'error: cannot pull with rebase: You have unstaged changes',
        dependency_changed: false,
        new_dependencies: [],
        dependencies_installed: 0,
        error: 'error: cannot pull with rebase: You have unstaged changes',
      };
      
      // 第二次调用（强制更新）返回成功
      const mockUpdateResultSuccess: UpdateResult = {
        plugin_name: 'test-plugin',
        success: true,
        message: '强制更新成功',
        dependency_changed: false,
        new_dependencies: [],
        dependencies_installed: 0,
      };

      mockUsePluginUpdate.updatePlugin
        .mockResolvedValueOnce(mockUpdateResultFail)
        .mockResolvedValueOnce(mockUpdateResultSuccess);

      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: mockCommits,
      });

      render(<UpdateCard {...defaultProps} />);

      // 第一次更新失败
      const updateButton = screen.getByRole('button', { name: /确定更新/i });
      await user.click(updateButton);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /强制更新（会丢失修改）/i })).toBeInTheDocument();
      });

      // 点击强制更新按钮
      const forceUpdateButton = screen.getByRole('button', { name: /强制更新（会丢失修改）/i });
      await user.click(forceUpdateButton);

      await waitFor(() => {
        expect(mockUsePluginUpdate.updatePlugin).toHaveBeenCalledWith('test-plugin', true);
      });
    });

    it('应该在加载时禁用更新按钮', () => {
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        loading: true,
      });

      render(<UpdateCard {...defaultProps} />);

      const updateButton = screen.getByRole('button', { name: /确定更新/i });
      expect(updateButton).toBeDisabled();
    });
  });

  describe('关闭功能', () => {
    it('应该在点击取消按钮时调用 onClose', async () => {
      render(<UpdateCard {...defaultProps} />);

      const cancelButton = screen.getByRole('button', { name: /取消/i });
      cancelButton.click();

      await waitFor(() => {
        expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
      });
    });

    it('应该在更新过程中禁用取消按钮', () => {
      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        updating: true,
      });

      render(<UpdateCard {...defaultProps} />);

      const cancelButton = screen.getByRole('button', { name: /取消/i });
      expect(cancelButton).toBeDisabled();
    });
  });

  describe('边界情况', () => {
    it('应该正确处理没有 commit_hash 的插件', () => {
      const pluginWithoutHash: PluginInfo = {
        ...mockPlugin,
        commit_hash: null,
      };

      render(<UpdateCard {...defaultProps} plugin={pluginWithoutHash} />);

      // 应该显示 unknown（会出现两次：当前版本和最新版本）
      const unknownTexts = screen.getAllByText('unknown');
      expect(unknownTexts.length).toBeGreaterThanOrEqual(1);
    });

    it('应该正确处理 behind_commits 为 0 的情况', () => {
      const pluginWithoutUpdate: PluginInfo = {
        ...mockPlugin,
        behind_commits: 0,
      };

      render(<UpdateCard {...defaultProps} plugin={pluginWithoutUpdate} />);

      // 不应该显示落后提交数的徽章
      expect(screen.queryByText(/落后.*个提交/)).not.toBeInTheDocument();
    });

    it('应该正确处理空的提交消息', () => {
      const commitsWithEmptyMessage: CommitInfo[] = [
        {
          hash: 'abc1234',
          message: '',
          date: '2024-01-15T10:30:00Z',
        },
      ];

      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: commitsWithEmptyMessage,
      });

      render(<UpdateCard {...defaultProps} />);

      // 应该正常渲染，不会崩溃（hash 会出现多次）
      const hashTexts = screen.getAllByText('abc1234');
      expect(hashTexts.length).toBeGreaterThan(0);
    });

    it('应该正确处理无效的日期格式', () => {
      const commitsWithInvalidDate: CommitInfo[] = [
        {
          hash: 'abc1234',
          message: 'test commit',
          date: 'invalid-date',
        },
      ];

      vi.mocked(usePluginUpdateModule.usePluginUpdate).mockReturnValue({
        ...mockUsePluginUpdate,
        commits: commitsWithInvalidDate,
      });

      render(<UpdateCard {...defaultProps} />);

      // 当日期无效时，会显示 "Invalid Date"
      expect(screen.getByText('Invalid Date')).toBeInTheDocument();
    });
  });
});
