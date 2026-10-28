//! 图片资源命令：缩略图、文件选择、图片转 data URL。


#[tauri::command]
pub(crate) fn get_sprite_thumbnail(path: String) -> Result<String, String> {
    use std::io::Read;

    let config_str;
    let first_frame_name;
    let png_data;

    if path.ends_with(".bgm") {
        // 从 .bgm zip 文件读取缩略图 (thumbnail.png)
        let data = std::fs::read(&path).map_err(|e| format!("读取 .bgm 失败: {}", e))?;
        let mut archive = zip::ZipArchive::new(std::io::Cursor::new(data))
            .map_err(|e| format!("解析 zip 失败: {}", e))?;

        let mut thumb_buf = Vec::new();
        {
            let thumb_entry = archive.by_name("thumbnail.png")
                .map_err(|e| format!("thumbnail.png 不存在: {}", e))?;
            let mut reader = std::io::BufReader::new(thumb_entry);
            reader.read_to_end(&mut thumb_buf).map_err(|e| e.to_string())?;
        }
        png_data = thumb_buf;
    } else if path.ends_with(".bgs") {
        // 从 .bgs zip 文件读取第一帧
        let data = std::fs::read(&path).map_err(|e| format!("读取 .bgs 失败: {}", e))?;
        let mut archive = zip::ZipArchive::new(std::io::Cursor::new(data))
            .map_err(|e| format!("解析 zip 失败: {}", e))?;

        let mut config_buf = String::new();
        {
            let config_entry = archive.by_name("config.json")
                .map_err(|e| format!("config.json 不存在: {}", e))?;
            let mut reader = std::io::BufReader::new(config_entry);
            reader.read_to_string(&mut config_buf).map_err(|e| e.to_string())?;
        }
        config_str = config_buf;

        let config: serde_json::Value = serde_json::from_str(&config_str)
            .map_err(|e| format!("解析 config.json 失败: {}", e))?;
        let frames = config["frames"].as_array()
            .ok_or("config.json 中没有 frames 字段")?;
        // 默认渲染帧（编辑器选中帧持久化字段），缺省回退第一帧
        let default_frame = config["defaultFrame"].as_str()
            .and_then(|d| frames.iter().find(|f| f.as_str() == Some(d)))
            .or_else(|| frames.first());
        first_frame_name = default_frame
            .ok_or("frames 为空")?
            .as_str()
            .ok_or("frames[0] 不是字符串")?.to_string();

        let mut png_buf = Vec::new();
        {
            let mut png_entry = archive.by_name(&first_frame_name)
                .map_err(|e| format!("第一帧 {} 不存在: {}", first_frame_name, e))?;
            png_entry.read_to_end(&mut png_buf).map_err(|e| e.to_string())?;
        }
        png_data = png_buf;
    } else if path.ends_with(".png") || path.ends_with(".jpg") || path.ends_with(".jpeg")
        || path.ends_with(".gif") || path.ends_with(".bmp") || path.ends_with(".webp") {
        // 常规图片文件：直接读取
        png_data = std::fs::read(&path)
            .map_err(|e| format!("读取图片失败: {}", e))?;
    } else {
        // 从解压后的目录读取
        let config_path = format!("{}/config.json", path);
        config_str = std::fs::read_to_string(&config_path)
            .map_err(|e| format!("读取 config.json 失败: {}", e))?;

        let config: serde_json::Value = serde_json::from_str(&config_str)
            .map_err(|e| format!("解析 config.json 失败: {}", e))?;
        let frames = config["frames"].as_array()
            .ok_or("config.json 中没有 frames 字段")?;
        // 默认渲染帧（编辑器选中帧持久化字段），缺省回退第一帧
        let default_frame = config["defaultFrame"].as_str()
            .and_then(|d| frames.iter().find(|f| f.as_str() == Some(d)))
            .or_else(|| frames.first());
        first_frame_name = default_frame
            .ok_or("frames 为空")?
            .as_str()
            .ok_or("frames[0] 不是字符串")?.to_string();

        let frame_path = format!("{}/{}", path, first_frame_name);
        png_data = std::fs::read(&frame_path)
            .map_err(|e| format!("读取第一帧 {} 失败: {}", first_frame_name, e))?;
    }

    // 转为 base64 data URL
    use base64::Engine;
    let b64 = base64::engine::general_purpose::STANDARD.encode(&png_data);
    Ok(format!("data:image/png;base64,{}", b64))
}

#[tauri::command]
pub(crate) async fn pick_image_file(app: tauri::AppHandle) -> Result<Option<String>, String> {
    use tauri_plugin_dialog::DialogExt;

    // 必须是 async 命令：blocking_pick_file 在主线程（同步命令）调用会在 macOS 上死锁
    let path = app.dialog()
        .file()
        .add_filter("图片", &["png", "jpg", "jpeg", "bmp", "gif", "svg"])
        .blocking_pick_file();

    Ok(path.map(|p| p.to_string()))
}

#[tauri::command]
pub(crate) async fn pick_files(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    use std::sync::mpsc;

    let (tx, rx) = mpsc::channel();
    app.dialog()
        .file()
        .pick_files(move |paths| {
            let _ = tx.send(paths);
        });

    let paths = rx.recv()
        .map_err(|_| "选择文件取消".to_string())?;

    Ok(paths.map(|ps| ps.iter().map(|p| p.to_string()).collect()).unwrap_or_default())
}

/// 多选图片（图块上传：一次选多张，全部按图块素材处理）
#[tauri::command]
pub(crate) async fn pick_image_files(app: tauri::AppHandle) -> Result<Vec<String>, String> {
    use tauri_plugin_dialog::DialogExt;
    use std::sync::mpsc;

    let (tx, rx) = mpsc::channel();
    app.dialog()
        .file()
        .add_filter("图片", &["png", "jpg", "jpeg", "bmp", "gif", "svg"])
        .pick_files(move |paths| {
            let _ = tx.send(paths);
        });

    let paths = rx.recv()
        .map_err(|_| "选择文件取消".to_string())?;

    Ok(paths.map(|ps| ps.iter().map(|p| p.to_string()).collect()).unwrap_or_default())
}

#[tauri::command]
pub(crate) fn read_image_as_data_url(path: String) -> Result<String, String> {
    use base64::Engine;

    let data = std::fs::read(&path).map_err(|e| format!("读取图片失败: {}", e))?;
    let b64 = base64::engine::general_purpose::STANDARD.encode(&data);
    Ok(format!("data:{};base64,{}", image_mime(&path), b64))
}

/// 批量读图（.bgs 逐帧预载用）：一次 IPC 往返读取全部路径，
/// 每项失败返回 null（与前端逐张失败语义一致），不因单张失败中断整批
#[tauri::command]
pub(crate) fn read_images_as_data_urls(paths: Vec<String>) -> Vec<Option<String>> {
    use base64::Engine;

    paths
        .iter()
        .map(|p| {
            std::fs::read(p).ok().map(|data| {
                let b64 = base64::engine::general_purpose::STANDARD.encode(&data);
                format!("data:{};base64,{}", image_mime(p), b64)
            })
        })
        .collect()
}

fn image_mime(path: &str) -> &'static str {
    if path.ends_with(".jpg") || path.ends_with(".jpeg") {
        "image/jpeg"
    } else if path.ends_with(".bmp") {
        "image/bmp"
    } else if path.ends_with(".gif") {
        "image/gif"
    } else if path.ends_with(".svg") {
        "image/svg+xml"
    } else {
        "image/png"
    }
}
