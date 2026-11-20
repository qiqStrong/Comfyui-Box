/* eslint-disable no-restricted-syntax */
/**
 * DependencyCard 组件单元测试
 * 
 * 测试依赖信息渲染、按钮状态、安装流程和关闭回调
 * 验证需求: 3.2, 3.3, 3.4
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DependencyCard } from '../DependencyCard';
import * as useDependenciesModule from '@/hooks/useDependencies';
import type { Dependency } from '@/types/plugin';

// Mock useDependencies Hook
vi.mock('@/hooks/useDependencies');

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
    Package: () => <span data-testid="package-icon" />,
    X: () => <span data-testid="close-icon" />,
  }
});

describe('DependencyCard', () => {
  // 默认 mock 返回值
  const mockUseDependencies = {
    dependencies: [] as Dependency[],
    loading: false,
    installing: null,
    error: null,
    loadDependencies: vi.fn(),
    installDependency: vi.fn(),
    clearDependencies: vi.fn(),
  };

  // 默认 props
  const defaultProps = {
    pluginName: 'test-plugin',
    onClose: vi.fn(),
    onDependencyViewed: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // 设置默认 mock
    vi.mocked(useDependenciesModule.useDependencies).mockReturnValue(mockUseDependencies);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('组件渲染', () => {
    it('应该正确渲染模态窗口标题和描述', () => {
      render(<DependencyCard {...defaultProps} />);

      expect(screen.getByTestId('modal-title')).toHaveTextContent('test-plugin - 依赖列表');
      expect(screen.getByTestId('modal-description')).toHaveTextContent(
        '查看和安装插件所需的 Python 依赖包'
      );
    });

    it('应该在组件挂载时加载依赖列表', () => {
      render(<DependencyCard {...defaultProps} />);

      expect(mockUseDependencies.loadDependencies).toHaveBeenCalledWith('test-plugin');
      expect(mockUseDependencies.loadDependencies).toHaveBeenCalledTimes(1);
    });

    it('应该在组件卸载时清除依赖列表', () => {
      const { unmount } = render(<DependencyCard {...defaultProps} />);

      unmount();

      expect(mockUseDependencies.clearDependencies).toHaveBeenCalledTimes(1);
    });
  });

  describe('加载状态', () => {
    it('应该在加载时显示加载指示器', () => {
      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        loading: true,
      });

      render(<DependencyCard {...defaultProps} />);

      expect(screen.getByTestId('loading')).toBeInTheDocument();
      expect(screen.getByText('加载依赖列表中...')).toBeInTheDocument();
    });
  });

  describe('错误状态', () => {
    it('应该在加载失败时显示错误信息', () => {
      const errorMessage = '网络连接失败';
      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        error: errorMessage,
      });

      render(<DependencyCard {...defaultProps} />);

      expect(screen.getByText('加载失败')).toBeInTheDocument();
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });
  });

  describe('空依赖列表', () => {
    it('应该在没有依赖时显示提示信息', () => {
      render(<DependencyCard {...defaultProps} />);

      expect(screen.getByTestId('package-icon')).toBeInTheDocument();
      expect(screen.getByText('该插件没有依赖')).toBeInTheDocument();
    });
  });

  describe('依赖信息渲染', () => {
    it('应该正确渲染已安装且版本匹配的依赖', () => {
      const dependencies: Dependency[] = [
        {
          package: 'numpy',
          version: '>=1.20.0',
          installed: true,
          installed_version: '1.24.0',
          version_match: true,
          message: '已安装',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      render(<DependencyCard {...defaultProps} />);

      // 验证包名
      expect(screen.getByText('numpy')).toBeInTheDocument();

      // 验证版本信息
      expect(screen.getByText('要求版本:')).toBeInTheDocument();
      expect(screen.getByText('>=1.20.0')).toBeInTheDocument();
      expect(screen.getByText('已安装版本:')).toBeInTheDocument();
      expect(screen.getByText('1.24.0')).toBeInTheDocument();

      // 验证状态消息（使用 getAllByText 因为文本出现多次）
      const statusTexts = screen.getAllByText('已安装');
      expect(statusTexts.length).toBeGreaterThan(0);

      // 验证按钮状态（已安装应该禁用）
      const installButton = screen.getByRole('button', { name: /已安装/i });
      expect(installButton).toBeDisabled();
    });

    it('应该正确渲染已安装但版本不匹配的依赖', () => {
      const dependencies: Dependency[] = [
        {
          package: 'torch',
          version: '>=2.0.0',
          installed: true,
          installed_version: '1.13.0',
          version_match: false,
          message: '版本不匹配',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      render(<DependencyCard {...defaultProps} />);

      // 验证包名
      expect(screen.getByText('torch')).toBeInTheDocument();

      // 验证版本信息
      expect(screen.getByText('>=2.0.0')).toBeInTheDocument();
      expect(screen.getByText('1.13.0')).toBeInTheDocument();

      // 验证状态消息（使用 getAllByText 因为文本出现多次）
      const statusTexts = screen.getAllByText('版本不匹配');
      expect(statusTexts.length).toBeGreaterThan(0);

      // 验证按钮状态（版本不匹配应该可以安装）
      const installButton = screen.getByRole('button', { name: /^安装$/i });
      expect(installButton).not.toBeDisabled();
    });

    it('应该正确渲染未安装的依赖', () => {
      const dependencies: Dependency[] = [
        {
          package: 'opencv-python',
          version: '>=4.5.0',
          installed: false,
          installed_version: null,
          version_match: false,
          message: '未安装',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      render(<DependencyCard {...defaultProps} />);

      // 验证包名
      expect(screen.getByText('opencv-python')).toBeInTheDocument();

      // 验证版本信息
      expect(screen.getByText('>=4.5.0')).toBeInTheDocument();

      // 不应该显示已安装版本
      expect(screen.queryByText('已安装版本:')).not.toBeInTheDocument();

      // 验证按钮状态（未安装应该可以安装）
      const installButton = screen.getByRole('button', { name: /安装/i });
      expect(installButton).not.toBeDisabled();
    });

    it('应该正确渲染多个依赖', () => {
      const dependencies: Dependency[] = [
        {
          package: 'numpy',
          version: '>=1.20.0',
          installed: true,
          installed_version: '1.24.0',
          version_match: true,
          message: '已安装',
        },
        {
          package: 'pillow',
          version: '>=9.0.0',
          installed: false,
          installed_version: null,
          version_match: false,
          message: '未安装',
        },
        {
          package: 'torch',
          version: '>=2.0.0',
          installed: true,
          installed_version: '1.13.0',
          version_match: false,
          message: '版本不匹配',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      render(<DependencyCard {...defaultProps} />);

      // 验证所有包名都显示
      expect(screen.getByText('numpy')).toBeInTheDocument();
      expect(screen.getByText('pillow')).toBeInTheDocument();
      expect(screen.getByText('torch')).toBeInTheDocument();
    });
  });

  describe('安装功能', () => {
    it('应该在点击安装按钮时调用 installDependency', async () => {
      const user = userEvent.setup();
      const dependencies: Dependency[] = [
        {
          package: 'pillow',
          version: '>=9.0.0',
          installed: false,
          installed_version: null,
          version_match: false,
          message: '未安装',
        },
      ];

      mockUseDependencies.installDependency.mockResolvedValue(true);

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      render(<DependencyCard {...defaultProps} />);

      const installButton = screen.getByRole('button', { name: /安装/i });
      await user.click(installButton);

      await waitFor(() => {
        expect(mockUseDependencies.installDependency).toHaveBeenCalledWith(
          'test-plugin',
          'pillow',
          '>=9.0.0'
        );
      });
    });

    it('应该在安装过程中显示加载状态', () => {
      const dependencies: Dependency[] = [
        {
          package: 'pillow',
          version: '>=9.0.0',
          installed: false,
          installed_version: null,
          version_match: false,
          message: '未安装',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
        installing: 'pillow',
      });

      render(<DependencyCard {...defaultProps} />);

      expect(screen.getByText('安装中')).toBeInTheDocument();
      const installButton = screen.getByRole('button', { name: /安装中/i });
      expect(installButton).toBeDisabled();
    });

    it('应该在安装其他依赖时不影响当前依赖的按钮', () => {
      const dependencies: Dependency[] = [
        {
          package: 'numpy',
          version: '>=1.20.0',
          installed: false,
          installed_version: null,
          version_match: false,
          message: '未安装',
        },
        {
          package: 'pillow',
          version: '>=9.0.0',
          installed: false,
          installed_version: null,
          version_match: false,
          message: '未安装',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
        installing: 'pillow',
      });

      render(<DependencyCard {...defaultProps} />);

      const buttons = screen.getAllByRole('button', { name: /安装/i });
      // numpy 的按钮应该可用
      expect(buttons[0]).not.toBeDisabled();
    });
  });

  describe('关闭功能', () => {
    it('应该在点击关闭按钮时调用 onDependencyViewed 和 onClose', async () => {
      const user = userEvent.setup();
      render(<DependencyCard {...defaultProps} />);

      // 获取底部的关闭按钮（不是模态窗口的关闭按钮）
      const buttons = screen.getAllByRole('button', { name: /关闭/i });
      const closeButton = buttons[buttons.length - 1]; // 底部的关闭按钮
      await user.click(closeButton);

      expect(defaultProps.onDependencyViewed).toHaveBeenCalledTimes(1);
      expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
    });

    it('应该在点击模态窗口关闭按钮时调用回调', async () => {
      const user = userEvent.setup();
      render(<DependencyCard {...defaultProps} />);

      const modalCloseButton = screen.getByTestId('modal-close');
      await user.click(modalCloseButton);

      expect(defaultProps.onDependencyViewed).toHaveBeenCalledTimes(1);
      expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('边界情况', () => {
    it('应该正确处理没有 installed_version 的已安装依赖', () => {
      const dependencies: Dependency[] = [
        {
          package: 'test-package',
          version: '>=1.0.0',
          installed: true,
          installed_version: null,
          version_match: true,
          message: '已安装',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      render(<DependencyCard {...defaultProps} />);

      // 不应该显示已安装版本
      expect(screen.queryByText('已安装版本:')).not.toBeInTheDocument();
    });

    it('应该正确处理没有 message 的依赖', () => {
      const dependencies: Dependency[] = [
        {
          package: 'test-package',
          version: '>=1.0.0',
          installed: false,
          installed_version: null,
          version_match: false,
          message: '',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      render(<DependencyCard {...defaultProps} />);

      // 应该正常渲染，不会崩溃
      expect(screen.getByText('test-package')).toBeInTheDocument();
    });

    it('应该正确处理特殊字符的包名', () => {
      const dependencies: Dependency[] = [
        {
          package: 'opencv-python-headless',
          version: '>=4.5.0',
          installed: false,
          installed_version: null,
          version_match: false,
          message: '未安装',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      render(<DependencyCard {...defaultProps} />);

      expect(screen.getByText('opencv-python-headless')).toBeInTheDocument();
    });
  });

  describe('优化查看依赖交互', () => {
    it('应该在组件挂载时立即加载依赖（从缓存）', () => {
      render(<DependencyCard {...defaultProps} />);

      // 验证立即调用了 loadDependencies
      expect(mockUseDependencies.loadDependencies).toHaveBeenCalledWith('test-plugin');
      expect(mockUseDependencies.loadDependencies).toHaveBeenCalledTimes(1);
    });

    it('应该在关闭时调用 onDependencyViewed（标记为已查看）', async () => {
      const user = userEvent.setup();
      render(<DependencyCard {...defaultProps} />);

      // 点击关闭按钮
      const buttons = screen.getAllByRole('button', { name: /关闭/i });
      const closeButton = buttons[buttons.length - 1];
      await user.click(closeButton);

      // 验证调用了 onDependencyViewed（清除更新标记）
      expect(defaultProps.onDependencyViewed).toHaveBeenCalledTimes(1);
    });

    it('应该在关闭时同时调用 onClose', async () => {
      const user = userEvent.setup();
      render(<DependencyCard {...defaultProps} />);

      // 点击关闭按钮
      const buttons = screen.getAllByRole('button', { name: /关闭/i });
      const closeButton = buttons[buttons.length - 1];
      await user.click(closeButton);

      // 验证同时调用了 onClose
      expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
    });

    it('应该在打开后立即显示缓存的依赖数据（< 50ms）', () => {
      const dependencies: Dependency[] = [
        {
          package: 'numpy',
          version: '>=1.20.0',
          installed: true,
          installed_version: '1.24.0',
          version_match: true,
          message: '已安装',
        },
      ];

      vi.mocked(useDependenciesModule.useDependencies).mockReturnValue({
        ...mockUseDependencies,
        dependencies,
      });

      const startTime = performance.now();
      render(<DependencyCard {...defaultProps} />);
      const endTime = performance.now();

      // 验证渲染时间 < 50ms
      expect(endTime - startTime).toBeLessThan(50);

      // 验证数据已显示
      expect(screen.getByText('numpy')).toBeInTheDocument();
    });

    it('应该在组件卸载时清除依赖列表', () => {
      const { unmount } = render(<DependencyCard {...defaultProps} />);

      unmount();

      // 验证调用了 clearDependencies
      expect(mockUseDependencies.clearDependencies).toHaveBeenCalledTimes(1);
    });
  });
});
