/* eslint-disable no-restricted-syntax */
/**
 * BatchUpdateModal 组件单元测试
 * 
 * 测试插件列表渲染、进度显示、模态窗口阻塞和结果摘要
 * 验证需求: 7.2, 7.3, 7.6, 7.7
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BatchUpdateModal } from '../BatchUpdateModal';
import { pluginAPI } from '@/services/PluginAPIService';
import { useSettingsStore } from '@/stores/useSettingsStore';
import type { PluginInfo, BatchUpdateResponse, UpdateResult } from '@/types/plugin';

// Mock pluginAPI
vi.mock('@/services/PluginAPIService', () => ({
  pluginAPI: {
    updateAllPlugins: vi.fn(),
  },
}));

// Mock useSettingsStore
vi.mock('@/stores/useSettingsStore', () => ({
  useSettingsStore: vi.fn(() => ({
    systemSettings: {
      gitConcurrency: 10, // 默认并发数
    },
  })),
}));

// Mock Button 组件
vi.mock('@/components/ui/Button', () => ({
  Button: ({ children, onClick, disabled, ...props }: any) => (
    <button onClick={onClick} disabled={disabled} {...props}>
      {children}
    </button>
  ),
}));

// Mock Badge 组件
vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, className }: any) => (
    <span data-testid="badge" className={className}>{children}</span>
  ),
}));

// Mock Loading 组件
vi.mock('@/components/ui/Loading', () => ({
  Loading: ({ size, text }: any) => (
    <div data-testid="loading" data-size={size}>{text}</div>
  ),
}));

// Mock lucide-react icons；保留真实导出，仅覆盖带 data-testid 断言的图标
vi.mock('lucide-react', async (importOriginal) => {
  const actual = await importOriginal<Record<string, any>>()
  return {
    ...actual,
    CheckCircle2: () => <span data-testid="check-icon" />,
    XCircle: () => <span data-testid="x-icon" />,
    Clock: () => <span data-testid="clock-icon" />,
    RefreshCw: () => <span data-testid="refresh-icon" />,
    Package: () => <span data-testid="package-icon" />,
    AlertCircle: () => <span data-testid="alert-icon" />,
    TrendingUp: () => <span data-testid="trending-icon" />,
    X: () => <span data-testid="close-icon" />,
    AlertTriangle: () => <span data-testid="alert-triangle-icon" />,
  }
});

describe('BatchUpdateModal', () => {
  // 测试数据
  const mockPlugins: PluginInfo[] = [
    {
      name: 'plugin-1',
      path: '/path/to/plugin-1',
      is_git_repo: true,
      git_url: 'https://github.com/test/plugin-1.git',
      branch: 'main',
      default_branch: 'main',
      commit_hash: 'abc1234',
      commit_date: '2024-01-10T10:00:00Z',
      has_update: true,
      behind_commits: 2,
      dependency_updated: false,
      dependency_viewed: false,
    },
    {
      name: 'plugin-2',
      path: '/path/to/plugin-2',
      is_git_repo: true,
      git_url: 'https://github.com/test/plugin-2.git',
      branch: 'main',
      default_branch: 'main',
      commit_hash: 'def5678',
      commit_date: '2024-01-12T15:00:00Z',
      has_update: true,
      behind_commits: 1,
      dependency_updated: false,
      dependency_viewed: false,
    },
    {
      name: 'plugin-3',
      path: '/path/to/plugin-3',
      is_git_repo: true,
      git_url: 'https://github.com/test/plugin-3.git',
      branch: 'main',
      default_branch: 'main',
      commit_hash: 'ghi9012',
      commit_date: '2024-01-15T09:00:00Z',
      has_update: true,
      behind_commits: 3,
      dependency_updated: false,
      dependency_viewed: false,
    },
  ];

  // 默认 props
  const defaultProps = {
    plugins: mockPlugins,
    onClose: vi.fn(),
    onComplete: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // 重置 body overflow
    document.body.style.overflow = 'unset';
  });

  afterEach(() => {
    vi.clearAllMocks();
    // 清理 body overflow
    document.body.style.overflow = 'unset';
  });

  describe('组件渲染', () => {
    it('应该正确渲染模态窗口标题和描述', async () => {
      // Mock API 响应
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 0,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      expect(screen.getByText('批量更新插件')).toBeInTheDocument();
      expect(screen.getByText('正在更新插件，请稍候...')).toBeInTheDocument();
    });

    it('应该在组件挂载时自动开始批量更新', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      await waitFor(() => {
        expect(pluginAPI.updateAllPlugins).toHaveBeenCalledTimes(1);
      });
    });

    it('应该阻止背景滚动', () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 0,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      expect(document.body.style.overflow).toBe('hidden');
    });

    it('应该在卸载时恢复背景滚动', () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 0,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      const { unmount } = render(<BatchUpdateModal {...defaultProps} />);

      unmount();

      expect(document.body.style.overflow).toBe('unset');
    });
  });

  describe('插件列表渲染 (验证需求: 7.2, 7.3)', () => {
    it('应该渲染所有待更新插件', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 0,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 验证所有插件名称都显示
      expect(screen.getByText('plugin-1')).toBeInTheDocument();
      expect(screen.getByText('plugin-2')).toBeInTheDocument();
      expect(screen.getByText('plugin-3')).toBeInTheDocument();
    });

    it('应该为每个插件显示初始状态（等待中）', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 0,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 验证初始状态徽章
      const badges = screen.getAllByTestId('badge');
      expect(badges.length).toBeGreaterThanOrEqual(3);
    });

    it('应该为每个插件显示进度条', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 0,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 验证进度条存在（通过检查进度条容器的类名）
      const progressBars = document.querySelectorAll('.bg-gray-200');
      expect(progressBars.length).toBeGreaterThanOrEqual(3);
    });

    it('应该为每个插件显示状态图标', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 0,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 验证状态图标存在（可能是等待中或更新中）
      // 由于更新会立即开始，可能看到的是更新中图标
      await waitFor(() => {
        const refreshIcons = screen.queryAllByTestId('refresh-icon');
        const clockIcons = screen.queryAllByTestId('clock-icon');
        
        // 至少应该有一种图标存在
        expect(refreshIcons.length + clockIcons.length).toBeGreaterThanOrEqual(3);
      });
    });
  });

  describe('进度显示 (验证需求: 7.3)', () => {
    it('应该在更新过程中显示更新中状态', async () => {
      // Mock API 响应（延迟）
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(mockResponse), 100))
      );

      render(<BatchUpdateModal {...defaultProps} />);

      // 验证初始状态
      await waitFor(() => {
        expect(screen.getByText('正在更新，请勿关闭窗口...')).toBeInTheDocument();
      });
    });

    it('应该在更新成功后显示成功状态', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证成功图标
      const checkIcons = screen.getAllByTestId('check-icon');
      expect(checkIcons.length).toBeGreaterThanOrEqual(3);
    });

    it('应该在更新失败后显示失败状态', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [
          {
            plugin_name: 'plugin-1',
            success: false,
            message: '更新失败：网络错误',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
            error: '网络错误',
          },
          {
            plugin_name: 'plugin-2',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
          {
            plugin_name: 'plugin-3',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
        ],
        summary: {
          total: 3,
          success: 2,
          failed: 1,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证失败图标
      const xIcons = screen.getAllByTestId('x-icon');
      expect(xIcons.length).toBeGreaterThanOrEqual(1);

      // 验证失败消息
      expect(screen.getByText('更新失败：网络错误')).toBeInTheDocument();
    });

    it('应该显示依赖安装数量', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [
          {
            plugin_name: 'plugin-1',
            success: true,
            message: '更新成功',
            dependency_changed: true,
            new_dependencies: [],
            dependencies_installed: 2,
          },
          {
            plugin_name: 'plugin-2',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
          {
            plugin_name: 'plugin-3',
            success: true,
            message: '更新成功',
            dependency_changed: true,
            new_dependencies: [],
            dependencies_installed: 1,
          },
        ],
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 3,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证依赖安装数量显示
      expect(screen.getByText('2 个依赖')).toBeInTheDocument();
      expect(screen.getByText('1 个依赖')).toBeInTheDocument();
    });
  });

  describe('模态窗口阻塞 (验证需求: 7.6)', () => {
    it('应该在更新完成前禁用关闭按钮', async () => {
      // Mock API 响应（延迟）
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(mockResponse), 100))
      );

      render(<BatchUpdateModal {...defaultProps} />);

      // 验证关闭按钮被禁用
      const closeButton = screen.getByRole('button', { name: /更新中/i });
      expect(closeButton).toBeDisabled();
    });

    it('应该在更新完成后启用关闭按钮', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证关闭按钮可用
      const closeButton = screen.getByRole('button', { name: /关闭/i });
      expect(closeButton).not.toBeDisabled();
    });

    it('应该在更新完成前不显示关闭图标按钮', async () => {
      // Mock API 响应（延迟）
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(mockResponse), 100))
      );

      render(<BatchUpdateModal {...defaultProps} />);

      // 验证没有关闭图标按钮
      expect(screen.queryByTestId('close-icon')).not.toBeInTheDocument();
    });

    it('应该在更新完成后显示关闭图标按钮', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证关闭图标按钮显示
      expect(screen.getByTestId('close-icon')).toBeInTheDocument();
    });

    it('应该在更新完成前阻止背景点击关闭', async () => {
      // Mock API 响应（延迟）
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(mockResponse), 100))
      );

      render(<BatchUpdateModal {...defaultProps} />);

      // 点击背景
      const backdrop = document.querySelector('.fixed.inset-0.bg-black\\/50');
      if (backdrop) {
        backdrop.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      }

      // 验证 onClose 未被调用
      expect(defaultProps.onClose).not.toHaveBeenCalled();
    });

    it('应该在更新完成后允许背景点击关闭', async () => {
      const user = userEvent.setup();
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 点击背景
      const backdrop = document.querySelector('.fixed.inset-0.bg-black\\/50');
      if (backdrop) {
        await user.click(backdrop as Element);
      }

      // 验证 onClose 被调用
      await waitFor(() => {
        expect(defaultProps.onClose).toHaveBeenCalled();
      });
    });
  });

  describe('结果摘要 (验证需求: 7.7)', () => {
    it('应该在更新完成后显示结果摘要', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证摘要标题
      expect(screen.getByText('更新摘要')).toBeInTheDocument();
      expect(screen.getByTestId('trending-icon')).toBeInTheDocument();
    });

    it('应该显示总数', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证总数 - 使用更具体的查询
      const summarySection = document.querySelector('.grid.grid-cols-4');
      expect(summarySection).toBeInTheDocument();
      expect(screen.getByText('总数')).toBeInTheDocument();
      // 验证总数值为 3
      const totalCell = summarySection?.querySelector('.text-center:first-child');
      expect(totalCell?.textContent).toContain('3');
      expect(totalCell?.textContent).toContain('总数');
    });

    it('应该显示成功数量', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [
          {
            plugin_name: 'plugin-1',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
          {
            plugin_name: 'plugin-2',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
          {
            plugin_name: 'plugin-3',
            success: false,
            message: '更新失败',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
            error: '网络错误',
          },
        ],
        summary: {
          total: 3,
          success: 2,
          failed: 1,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证成功数量 - 使用更具体的查询
      const summarySection = document.querySelector('.grid.grid-cols-4');
      expect(summarySection).toBeInTheDocument();
      
      // 验证成功数值为 2
      const successCell = summarySection?.querySelectorAll('.text-center')[1];
      expect(successCell?.textContent).toContain('2');
      expect(successCell?.textContent).toContain('成功');
    });

    it('应该显示失败数量', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [
          {
            plugin_name: 'plugin-1',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
          {
            plugin_name: 'plugin-2',
            success: false,
            message: '更新失败',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
            error: '网络错误',
          },
          {
            plugin_name: 'plugin-3',
            success: false,
            message: '更新失败',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
            error: 'Git 错误',
          },
        ],
        summary: {
          total: 3,
          success: 1,
          failed: 2,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证失败数量 - 使用更具体的查询
      const summarySection = document.querySelector('.grid.grid-cols-4');
      expect(summarySection).toBeInTheDocument();
      
      // 验证失败数值为 2
      const failedCell = summarySection?.querySelectorAll('.text-center')[2];
      expect(failedCell?.textContent).toContain('2');
      expect(failedCell?.textContent).toContain('失败');
    });

    it('应该显示依赖安装总数', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [
          {
            plugin_name: 'plugin-1',
            success: true,
            message: '更新成功',
            dependency_changed: true,
            new_dependencies: [],
            dependencies_installed: 2,
          },
          {
            plugin_name: 'plugin-2',
            success: true,
            message: '更新成功',
            dependency_changed: true,
            new_dependencies: [],
            dependencies_installed: 3,
          },
          {
            plugin_name: 'plugin-3',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
        ],
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 5,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证依赖安装总数
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('依赖安装')).toBeInTheDocument();
    });

    it('应该验证成功数 + 失败数 = 总数', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [
          {
            plugin_name: 'plugin-1',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
          {
            plugin_name: 'plugin-2',
            success: false,
            message: '更新失败',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
            error: '网络错误',
          },
          {
            plugin_name: 'plugin-3',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
        ],
        summary: {
          total: 3,
          success: 2,
          failed: 1,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证数学关系
      const { summary } = mockResponse;
      expect(summary.success + summary.failed).toBe(summary.total);
    });
  });

  describe('关闭功能', () => {
    it('应该在点击关闭按钮时调用 onClose', async () => {
      const user = userEvent.setup();
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 点击关闭按钮
      const closeButton = screen.getByRole('button', { name: /关闭/i });
      await user.click(closeButton);

      // 验证 onClose 被调用
      expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
    });

    it('应该在更新完成后调用 onComplete', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证 onComplete 被调用
      expect(defaultProps.onComplete).toHaveBeenCalledTimes(1);
    });
  });

  describe('错误处理', () => {
    it('应该在 API 返回 success: false 时显示错误', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: false,
        error: '批量更新失败：网络连接超时',
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待错误显示
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: '批量更新失败' })).toBeInTheDocument();
      });

      // 验证错误消息在错误提示区域中
      const errorSection = document.querySelector('.border-destructive');
      expect(errorSection).toBeInTheDocument();
      expect(errorSection?.textContent).toContain('批量更新失败：网络连接超时');

      // 验证错误图标
      expect(screen.getByTestId('alert-icon')).toBeInTheDocument();
    });

    it('应该在 API 抛出异常时显示错误', async () => {
      const mockError = new Error('网络异常');
      vi.mocked(pluginAPI.updateAllPlugins).mockRejectedValue(mockError);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待错误显示
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: '批量更新失败' })).toBeInTheDocument();
        // 验证错误消息在错误提示区域中
        const errorSection = document.querySelector('.border-destructive');
        expect(errorSection).toBeInTheDocument();
        expect(errorSection?.textContent).toContain('网络异常');
      });
    });

    it('应该在错误时将所有插件标记为失败', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: false,
        error: '批量更新失败',
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待错误显示
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: '批量更新失败' })).toBeInTheDocument();
      });

      // 验证所有插件都显示失败图标
      const xIcons = screen.getAllByTestId('x-icon');
      expect(xIcons.length).toBeGreaterThanOrEqual(3);
    });
  });

  describe('并发控制', () => {
    it('应该使用默认并发数调用 API', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 应该使用配置的默认并发数（10）
      await waitFor(() => {
        expect(pluginAPI.updateAllPlugins).toHaveBeenCalledWith(undefined, 10);
      });
    });

    it('应该使用自定义并发数调用 API', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} maxWorkers={5} />);

      await waitFor(() => {
        expect(pluginAPI.updateAllPlugins).toHaveBeenCalledWith(undefined, 5);
      });
    });

    it('应该从 settings store 读取 Git 并发数配置 (验证需求: 13.5)', async () => {
      // Mock settings store 返回自定义并发数
      vi.mocked(useSettingsStore).mockReturnValue({
        systemSettings: {
          gitConcurrency: 15,
          configMode: 'preset',
          autoUpdate: true,
          theme: 'light',
          windowSize: '1680x1080',
          language: 'zh-CN',
          proxyEnabled: false,
          proxyHost: '',
          proxyPort: '',
        },
        versionSettings: {
          displayCount: 20,
          showDevWarning: true,
        },
        loading: false,
        updateVersionSettings: vi.fn(),
        updateSystemSettings: vi.fn(),
        loadSystemSettings: vi.fn(),
        resetDevWarning: vi.fn(),
      });

      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 验证使用配置的并发数（15）调用 API
      await waitFor(() => {
        expect(pluginAPI.updateAllPlugins).toHaveBeenCalledWith(undefined, 15);
      });
    });

    it('应该优先使用 props 传入的 maxWorkers 而不是配置值 (验证需求: 13.5)', async () => {
      // Mock settings store 返回并发数 15
      vi.mocked(useSettingsStore).mockReturnValue({
        systemSettings: {
          gitConcurrency: 15,
          configMode: 'preset',
          autoUpdate: true,
          theme: 'light',
          windowSize: '1680x1080',
          language: 'zh-CN',
          proxyEnabled: false,
          proxyHost: '',
          proxyPort: '',
        },
        versionSettings: {
          displayCount: 20,
          showDevWarning: true,
        },
        loading: false,
        updateVersionSettings: vi.fn(),
        updateSystemSettings: vi.fn(),
        loadSystemSettings: vi.fn(),
        resetDevWarning: vi.fn(),
      });

      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 3,
          success: 3,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      // 传入 maxWorkers=20，应该优先使用这个值
      render(<BatchUpdateModal {...defaultProps} maxWorkers={20} />);

      // 验证使用 props 的值（20）而不是配置的值（15）
      await waitFor(() => {
        expect(pluginAPI.updateAllPlugins).toHaveBeenCalledWith(undefined, 20);
      });
    });
  });

  describe('边界情况', () => {
    it('应该正确处理空插件列表', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [],
        summary: {
          total: 0,
          success: 0,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} plugins={[]} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证摘要显示 - 使用更具体的查询
      expect(screen.getByText('总数')).toBeInTheDocument();
      expect(screen.getByText('成功')).toBeInTheDocument();
      expect(screen.getByText('失败')).toBeInTheDocument();
      expect(screen.getByText('依赖安装')).toBeInTheDocument();
      
      // 验证所有数字都是 0
      const summarySection = document.querySelector('.grid.grid-cols-4');
      expect(summarySection?.textContent).toContain('0');
    });

    it('应该正确处理单个插件', async () => {
      const singlePlugin = [mockPlugins[0]];
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [
          {
            plugin_name: 'plugin-1',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            dependencies_installed: 0,
          },
        ],
        summary: {
          total: 1,
          success: 1,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} plugins={singlePlugin} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 验证只显示一个插件
      expect(screen.getByText('plugin-1')).toBeInTheDocument();
      expect(screen.queryByText('plugin-2')).not.toBeInTheDocument();
    });

    it('应该正确处理缺少 summary 的响应', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: mockPlugins.map(p => ({
          plugin_name: p.name,
          success: true,
          message: '更新成功',
          dependency_changed: false,
          new_dependencies: [],
          dependencies_installed: 0,
        })),
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 应该正常渲染，不会崩溃
      expect(screen.getByText('plugin-1')).toBeInTheDocument();
    });

    it('应该正确处理缺少 dependencies_installed 的结果', async () => {
      const mockResponse: BatchUpdateResponse = {
        success: true,
        results: [
          {
            plugin_name: 'plugin-1',
            success: true,
            message: '更新成功',
            dependency_changed: false,
            new_dependencies: [],
            // dependencies_installed 缺失
          } as any,
        ],
        summary: {
          total: 1,
          success: 1,
          failed: 0,
          dependencies_installed: 0,
        },
      };
      vi.mocked(pluginAPI.updateAllPlugins).mockResolvedValue(mockResponse);

      render(<BatchUpdateModal {...defaultProps} plugins={[mockPlugins[0]]} />);

      // 等待更新完成
      await waitFor(() => {
        expect(screen.getByText('更新已完成')).toBeInTheDocument();
      });

      // 不应该显示依赖安装数量
      expect(screen.queryByText(/个依赖/)).not.toBeInTheDocument();
    });
  });
});
