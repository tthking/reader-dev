//! URL 路径归一化中间件（消除前端由于 URL 相对路径拼接、路由切换或 localStorage 脏值产生的子路径叠加）

use axum::{extract::Request, middleware::Next, response::Response};
use http::uri::PathAndQuery;

/// URL 路径归一化中间件：
/// 1. 若路径中包含 "/reader3/"（例如 "/sources/reader3/saveBookSources" 或 "/bookmarks/reader3/getBookmarks"），
///    将其截断重写为以 "/reader3/" 开头（如 "/reader3/saveBookSources"）。
/// 2. 若路径不包含 "/reader3/"，但以常见前端子路径（如 "/sources/", "/bookmarks/", "/replace/", "/book/"）开头且紧接着 API 端点，
///    将其重写为根端点路径。
pub async fn normalize_reader_path(mut req: Request, next: Next) -> Response {
    let uri = req.uri();
    let path = uri.path();

    let mut rewritten_path: Option<String> = None;

    if let Some(idx) = path.find("/reader3/") {
        if idx > 0 {
            rewritten_path = Some(path[idx..].to_string());
        }
    } else {
        // 前端虚拟子路由前缀兼容（如 /sources/saveBookSources -> /saveBookSources）
        const SUBPATHS: &[&str] = &[
            "/sources/",
            "/bookmarks/",
            "/replace/",
            "/settings/",
            "/explore/",
            "/login/",
            "/manage/",
            "/books/",
        ];
        for prefix in SUBPATHS {
            if path.starts_with(prefix) {
                let remainder = &path[prefix.len() - 1..]; // 保持以 '/' 开头
                rewritten_path = Some(remainder.to_string());
                break;
            }
        }
    }

    if let Some(new_path) = rewritten_path {
        let mut parts = uri.clone().into_parts();
        let pq_str = match parts.path_and_query {
            Some(ref pq) => match pq.query() {
                Some(q) => format!("{}?{}", new_path, q),
                None => new_path,
            },
            None => new_path,
        };
        if let Ok(new_pq) = PathAndQuery::from_maybe_shared(pq_str) {
            parts.path_and_query = Some(new_pq);
            if let Ok(new_uri) = http::Uri::from_parts(parts) {
                *req.uri_mut() = new_uri;
            }
        }
    }

    next.run(req).await
}
