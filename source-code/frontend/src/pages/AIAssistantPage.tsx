/**
 * AI 助手页面
 * 
 * 功能：
 * - 选项卡布局（多轮对话、日志分析、API 设置）
 * - 集成 TopicList 组件（左侧边栏）
 * - 集成 MessageList 组件
 * - 集成 InputArea 组件
 * - 流式响应显示（打字机效果）
 * 
 * 验证需求：1.1, 1.2, 1.3
 */

import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { TopicList } from '@/components/ai/TopicList'
import { MessageList } from '@/components/ai/MessageList'
import { InputArea } from '@/components/ai/InputArea'
import { APISettingsView } from '@/components/ai/APISettingsView'
import { ModelSelector } from '@/components/ai/ModelSelector'
import { PromptSelector } from '@/components/ai/PromptSelector'
import { PromptSettingsButton } from '@/components/ai/PromptSettingsButton'
import { PromptManagementDialog } from '@/components/ai/PromptManagementDialog'
import { SearchSettings } from '@/components/ai/SearchSettings'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScopeBadge } from '@/components/common/ScopeBadge'
import { Button } from '@/components/ui/Button'
import { MessageSquare, Settings, Globe, Bot } from 'lucide-react'
import { useTopicStore } from '@/stores/useTopicStore'
import { useSystemPromptStore } from '@/stores/useSystemPromptStore'

/**
 * AI 助手页面
 */
export default function AIAssistantPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('chat')
  const [searchSettingsOpen, setSearchSettingsOpen] = useState(false)
  const [promptManagementOpen, setPromptManagementOpen] = useState(false)
  const { currentTopicId } = useTopicStore()
  const { initializeDefaultPreset } = useSystemPromptStore()
  
  // 初始化默认预设（仅在首次启动时）
  useEffect(() => {
    initializeDefaultPreset()
  }, [initializeDefaultPreset])
  
  return (
    <div className="flex size-full flex-col overflow-hidden bg-background">
      {/* 页面标题区域 */}
      <div className="shrink-0 bg-surface px-6 pb-3 pt-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-primary shadow-plugin-button">
            <Bot className="size-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="from-plugin-primary to-plugin-primary-dark bg-gradient-to-r bg-clip-text text-xl font-bold leading-tight text-transparent">
              {t("aiAssistant.title")}
            </h1>
            <p className="text-xs leading-tight text-muted-foreground">{t("aiAssistant.subtitle")}</p>
          </div>
        </div>
      </div>

      {/* 选项卡导航和内容 */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex min-h-0 flex-1 flex-col">
        <div className="border-b border-border bg-surface px-6">
          <div className="flex items-center justify-between">
            {/* 左侧：标签栏 */}
            <TabsList className="h-10 justify-start rounded-none bg-transparent p-0">
              <TabsTrigger
                value="chat"
                className="data-[state=active]:border-plugin-primary data-[state=active]:text-plugin-primary rounded-none border-b-2 border-transparent px-5 text-sm text-muted-foreground transition-colors duration-200 data-[state=active]:bg-transparent"
              >
                <MessageSquare className="mr-1.5 size-3.5" />
                {t("aiAssistant.tabs.chat")}
              </TabsTrigger>
              <TabsTrigger
                value="settings"
                className="data-[state=active]:border-plugin-primary data-[state=active]:text-plugin-primary rounded-none border-b-2 border-transparent px-5 text-sm text-muted-foreground transition-colors duration-200 data-[state=active]:bg-transparent"
              >
                <Settings className="mr-1.5 size-3.5" />
                {t("aiAssistant.tabs.apiSettings")}
              </TabsTrigger>
            </TabsList>
            
            {/* 右侧：模型选择器、系统提示词选择器和搜索设置 */}
            {activeTab === 'chat' && (
              <div className="flex items-center gap-3 pb-0.5">
                <ScopeBadge category="ai" />
                {/* 模型配置 */}
                <div className="flex items-center gap-1.5">
                  <span className="whitespace-nowrap text-xs text-muted-foreground">
                    {t("aiAssistant.modelConfig")}
                  </span>
                  <ModelSelector 
                    topicId={currentTopicId} 
                    onNavigateToSettings={() => setActiveTab('settings')}
                  />
                </div>
                
                <div className="flex items-center gap-1.5">
                  <span className="whitespace-nowrap text-xs text-muted-foreground">
                    {t("aiAssistant.systemPrompt")}
                  </span>
                  <PromptSelector topicId={currentTopicId} />
                  <PromptSettingsButton onClick={() => setPromptManagementOpen(true)} />
                </div>
                
                {/* 搜索设置 */}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSearchSettingsOpen(true)}
                  className="h-8 px-2.5"
                  title={t("common.title.searchSettings")}
                >
                  <Globe className="size-3.5" />
                </Button>
              </div>
            )}
          </div>
        </div>
        
        {/* 多轮对话选项卡 */}
        <TabsContent value="chat" className="m-0 flex min-h-0 flex-1 bg-background">
          <div className="flex min-h-0 flex-1">
            {/* 左侧边栏：话题列表 */}
            <div className="w-64 border-r border-border bg-surface">
              <TopicList />
            </div>
            
            {/* 右侧主区域：消息列表和输入框 */}
            <div className="flex min-h-0 flex-1 flex-col bg-background">
              {/* 消息列表 */}
              <div className="flex-1 overflow-hidden">
                <MessageList />
              </div>
              
              {/* 输入区域 */}
              <InputArea />
            </div>
          </div>
        </TabsContent>
        
        {/* API 设置选项卡 */}
        <TabsContent value="settings" className="m-0 flex min-h-0 flex-1 overflow-hidden bg-background">
          <APISettingsView />
        </TabsContent>
      </Tabs>
      
      {/* 搜索设置弹窗 */}
      <SearchSettings 
        open={searchSettingsOpen} 
        onOpenChange={setSearchSettingsOpen} 
      />
      
      {/* 系统提示词管理弹窗 */}
      <PromptManagementDialog
        open={promptManagementOpen}
        onOpenChange={setPromptManagementOpen}
      />
    </div>
  )
}
