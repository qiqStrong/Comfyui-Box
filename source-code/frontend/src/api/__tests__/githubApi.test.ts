import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

import { fetchReleases } from '@/api/githubApi'

/**
 * 更新日志弹窗的数据来源：远端 Release 列表 + 随包分发的 version.json。
 *
 * 复现的缺陷：仓库里只有 v1.0.0 的 Release，而应用已经升到 V1.0.2，
 * 弹窗就会把 V1.0.0 标成「最新」，与标题里的当前版本自相矛盾。
 */

type Release = {
  id: number
  tag_name: string
  name: string
  body: string
  published_at: string
  html_url: string
  prerelease: boolean
  draft: boolean
}

function makeRelease(tag: string, publishedAt: string, name = tag): Release {
  return {
    id: Math.random(),
    tag_name: tag,
    name,
    body: `${name} 的更新内容`,
    published_at: publishedAt,
    html_url: 'https://github.com/qiqStrong/Comfyui-Box/releases',
    prerelease: false,
    draft: false
  }
}

function installBridge(options: {
  releases?: Release[]
  releasesFail?: boolean
  local?: { version: string; published_at: string; release_notes: string } | null
}) {
  const getGithubReleases = vi.fn(async () => {
    if (options.releasesFail) throw new Error('network down')
    return { success: true, releases: options.releases ?? [] }
  })
  const getLocalReleaseInfo = vi.fn(async () =>
    options.local
      ? { success: true, ...options.local }
      : { success: false }
  )

  ;(window as unknown as { pywebview: unknown }).pywebview = {
    api: {
      get_github_releases: getGithubReleases,
      get_local_release_info: getLocalReleaseInfo
    }
  }
  return { getGithubReleases, getLocalReleaseInfo }
}

describe('fetchReleases', () => {
  beforeEach(() => {
    delete (window as unknown as { pywebview?: unknown }).pywebview
  })

  afterEach(() => {
    delete (window as unknown as { pywebview?: unknown }).pywebview
  })

  it('远端只有旧版本时，把随包版本并进来并排在最前', async () => {
    installBridge({
      releases: [makeRelease('v1.0.0', '2026-11-04T06:34:09Z', 'Comfyui-Box V1.0.0')],
      local: {
        version: 'V1.0.2',
        published_at: '2026-11-11T02:34:00Z',
        release_notes: '# V1.0.2 更新日志'
      }
    })

    const releases = await fetchReleases()

    expect(releases).toHaveLength(2)
    expect(releases[0].tag_name).toBe('V1.0.2')
    expect(releases[0].body).toContain('V1.0.2')
    expect(releases[1].tag_name).toBe('v1.0.0')
  })

  it('远端已包含当前版本时不重复插入', async () => {
    installBridge({
      releases: [
        makeRelease('v1.0.2', '2026-11-11T02:34:00Z'),
        makeRelease('v1.0.1', '2026-11-08T02:00:00Z'),
        makeRelease('v1.0.0', '2026-11-04T06:34:09Z')
      ],
      local: {
        version: 'V1.0.2',
        published_at: '2026-11-11T02:34:00Z',
        release_notes: '# V1.0.2 更新日志'
      }
    })

    const releases = await fetchReleases()

    expect(releases.map((r) => r.tag_name)).toEqual(['v1.0.2', 'v1.0.1', 'v1.0.0'])
  })

  it('远端有新版本时仍按发布时间倒序，最多三条', async () => {
    installBridge({
      releases: [
        makeRelease('v1.0.3', '2026-11-20T00:00:00Z'),
        makeRelease('v1.0.2', '2026-11-11T02:34:00Z'),
        makeRelease('v1.0.1', '2026-11-08T02:00:00Z')
      ],
      local: {
        version: 'V1.0.2',
        published_at: '2026-11-11T02:34:00Z',
        release_notes: '# V1.0.2 更新日志'
      }
    })

    const releases = await fetchReleases()

    expect(releases).toHaveLength(3)
    expect(releases[0].tag_name).toBe('v1.0.3')
  })

  it('远端不可达时只返回随包版本', async () => {
    installBridge({
      releasesFail: true,
      local: {
        version: 'V1.0.2',
        published_at: '2026-11-11T02:34:00Z',
        release_notes: '# V1.0.2 更新日志'
      }
    })

    const releases = await fetchReleases()

    expect(releases).toHaveLength(1)
    expect(releases[0].tag_name).toBe('V1.0.2')
  })

  it('两边都没有数据时返回空数组', async () => {
    installBridge({ releases: [], local: null })

    await expect(fetchReleases()).resolves.toEqual([])
  })
})
