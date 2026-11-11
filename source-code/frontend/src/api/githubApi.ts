export interface GitHubRelease {
  id: number
  tag_name: string
  name: string
  body: string
  published_at: string
  html_url: string
  prerelease: boolean
  draft: boolean
}

const MAX_RELEASES = 3

export const GITHUB_RELEASES_URL = 'https://github.com/qiqStrong/Comfyui-Box/releases'

/**
 * 用随应用分发的 version.json 兜底生成一条更新日志。
 * GitHub API 不可达（国内网络常见）或仓库还没有 Release 时使用。
 */
export async function fetchLocalRelease(): Promise<GitHubRelease | null> {
  const api = (window as { pywebview?: { api?: { get_local_release_info?: () => Promise<{ success: boolean; version?: string; published_at?: string; release_notes?: string }> } } }).pywebview?.api
  if (!api?.get_local_release_info) return null

  try {
    const local = await api.get_local_release_info()
    if (!local?.success || !local.release_notes) return null

    return {
      id: 0,
      tag_name: local.version || '',
      name: local.version || '',
      body: local.release_notes,
      published_at: local.published_at || '',
      html_url: GITHUB_RELEASES_URL,
      prerelease: false,
      draft: false,
    }
  } catch {
    return null
  }
}

export async function fetchReleases(): Promise<GitHubRelease[]> {
  let remote: GitHubRelease[] = []

  try {
    const result = await window.pywebview.api.get_github_releases(
      'qiqStrong',
      'Comfyui-Box',
      MAX_RELEASES
    )

    if (result.success && result.releases) {
      remote = result.releases.filter((release: GitHubRelease) => !release.draft)
    }
  } catch {
    // 网络异常时继续走本地兜底
  }

  // 仓库里可能只有老版本的 Release（新版本还没发），此时远端列表里没有当前版本，
  // 直接展示会出现「应用是 V1.0.2、日志却把 V1.0.0 标成最新」。
  // 这里把随包分发的 version.json 也并进来，按发布时间倒序取前 3 条。
  const local = await fetchLocalRelease()
  const merged = [...remote]
  if (local && !merged.some((item) => sameVersion(item.tag_name, local.tag_name))) {
    merged.push(local)
  }

  return merged
    .sort((a, b) => (b.published_at || '').localeCompare(a.published_at || ''))
    .slice(0, MAX_RELEASES)
}

/** 版本号比较时忽略大小写与 v 前缀（V1.0.2 / v1.0.2 视为同一个） */
function sameVersion(a: string, b: string): boolean {
  const normalize = (value: string) => value.trim().replace(/^v/i, '').toLowerCase()
  return normalize(a) === normalize(b)
}

export function parseReleaseBody(body: string): string[] {
  const lines = body.split('\n')
  const changes: string[] = []
  
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      const change = trimmed.substring(2).trim()
      if (change) {
        changes.push(change)
      }
    }
  }
  
  return changes.slice(0, 5)
}

export function formatReleaseDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
