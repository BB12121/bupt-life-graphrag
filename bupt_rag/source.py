"""Read a complete, immutable upstream snapshot; never follow external links."""

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import EXCLUDED, REPOSITORY, SOURCE_PREFIX
from .models import AppError


class GitHubSource:
    def __init__(self):
        self.client = requests.Session()
        self.client.headers["User-Agent"] = "bupt-life-graphrag/0.1"
        self.client.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 502, 503, 504])
            ),
        )

    def close(self):
        self.client.close()

    def _get(self, url):
        try:
            response = self.client.get(url, timeout=45)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            raise AppError("source_unavailable", "资料源读取失败；现有快照不变，请稍后重试。") from exc

    def resolve(self, ref):
        data = self._json(f"https://api.github.com/repos/{REPOSITORY}/commits/{quote(ref, safe='')}")
        sha = data.get("sha", "")
        if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise AppError("invalid_source", "上游未返回完整提交 SHA。")
        return sha

    def _json(self, url):
        try:
            data = self._get(url).json()
        except ValueError as exc:
            raise AppError("invalid_source", "上游返回了无效 JSON，不发布新版本。") from exc
        if not isinstance(data, dict):
            raise AppError("invalid_source", "上游返回了无效数据结构，不发布新版本。")
        return data

    def fetch(self, commit):
        tree = self._json(f"https://api.github.com/repos/{REPOSITORY}/git/trees/{commit}?recursive=1")
        if tree.get("truncated") or not isinstance(tree.get("tree"), list):
            raise AppError("incomplete_source", "上游文件清单不完整，不发布新版本。")
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or item.get("type") not in {"blob", "tree", "commit"}
            for item in tree["tree"]
        ):
            raise AppError("incomplete_source", "上游文件清单有无效条目，不发布新版本。")
        paths = sorted(
            item["path"]
            for item in tree["tree"]
            if (
                item["type"] == "blob"
                and item["path"].startswith(SOURCE_PREFIX)
                and item["path"].rsplit("/", 1)[-1] not in EXCLUDED
                and item["path"].endswith((".md", ".mdx"))
            )
        )
        if not paths or len(paths) > 200:
            raise AppError("invalid_source", "正文清单为空或超过首版容量，需人工检查。")

        def read(path):
            response = self._get(f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{quote(path)}")
            if len(response.content) > 2_000_000:
                raise AppError("invalid_source", "单篇正文超过 2MB，停止同步。")
            try:
                return path, response.content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise AppError("invalid_source", "正文不是有效的 UTF-8，不发布新版本。") from exc

        # Any failed file aborts the entire sync, including deletions.
        with ThreadPoolExecutor(max_workers=4) as pool:
            return dict(pool.map(read, paths))
