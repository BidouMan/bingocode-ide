//! 工程打包/解包（.bingo 文件）。


#[tauri::command]
pub(crate) fn pack_bingo(workspace_dir: String, output_path: String) -> Result<(), String> {
    use std::io::{Write, Read};
    use zip::write::FileOptions;

    let workspace = std::path::Path::new(&workspace_dir);
    if !workspace.exists() {
        return Err("工作目录不存在".to_string());
    }

    let output = std::path::Path::new(&output_path);
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("创建目录失败: {}", e))?;
    }

    let file = std::fs::File::create(output)
        .map_err(|e| format!("创建 .bc 文件失败: {}", e))?;
    let mut zip = zip::ZipWriter::new(file);
    let options = FileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated)
        .compression_level(Some(6));

    // 递归添加工作目录中的所有文件
    fn add_dir_to_zip(
        zip: &mut zip::ZipWriter<std::fs::File>,
        base: &std::path::Path,
        current: &std::path::Path,
        options: zip::write::FileOptions,
    ) -> Result<(), String> {
        let entries = std::fs::read_dir(current)
            .map_err(|e| format!("读取目录失败: {}", e))?;

        for entry in entries.flatten() {
            let path = entry.path();
            let name = path.strip_prefix(base)
                .map_err(|e| format!("路径错误: {}", e))?
                .to_string_lossy()
                .replace('\\', "/");

            if path.is_dir() {
                // 跳过隐藏目录和 __pycache__
                let dir_name = entry.file_name().to_string_lossy().to_string();
                if dir_name.starts_with('.') || dir_name == "__pycache__" {
                    continue;
                }
                add_dir_to_zip(zip, base, &path, options)?;
            } else {
                // 跳过隐藏文件和临时文件
                let file_name = entry.file_name().to_string_lossy().to_string();
                if file_name.starts_with('.') || file_name == ".temp_run.py" {
                    continue;
                }

                let mut f = std::fs::File::open(&path)
                    .map_err(|e| format!("打开文件失败 {}: {}", path.display(), e))?;
                let mut buffer = Vec::new();
                f.read_to_end(&mut buffer)
                    .map_err(|e| format!("读取文件失败: {}", e))?;

                zip.start_file(&name, options)
                    .map_err(|e| format!("创建 zip 条目失败: {}", e))?;
                zip.write_all(&buffer)
                    .map_err(|e| format!("写入 zip 失败: {}", e))?;
            }
        }
        Ok(())
    }

    add_dir_to_zip(&mut zip, workspace, workspace, options)?;
    zip.finish().map_err(|e| format!("完成 zip 写入失败: {}", e))?;

    Ok(())
}

#[tauri::command]
pub(crate) fn unpack_bingo(bingo_path: String, target_dir: String) -> Result<(), String> {
    let data = std::fs::read(&bingo_path)
        .map_err(|e| format!("读取 .bc 文件失败: {}", e))?;
    let mut archive = zip::ZipArchive::new(std::io::Cursor::new(data))
        .map_err(|e| format!("解析 .bc 文件失败: {}", e))?;

    let target = std::path::Path::new(&target_dir);
    std::fs::create_dir_all(target)
        .map_err(|e| format!("创建目标目录失败: {}", e))?;

    // 打开项目 = 用 .bc 内容整体替换工作目录。所有项目共用同一个工作目录
    // （~/BingoCodeIDE/Projects/default），解包前必须清空旧内容，
    // 否则上一个项目的角色/地图会残留在磁盘上，串到新打开的项目里
    // （资源管理器按磁盘目录扫描，保存时 pack_bingo 也会把残留文件一起打包）
    let entries = std::fs::read_dir(target)
        .map_err(|e| format!("读取目标目录失败: {}", e))?;
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            let _ = std::fs::remove_dir_all(&path);
        } else {
            let _ = std::fs::remove_file(&path);
        }
    }

    archive.extract(target)
        .map_err(|e| format!("解压 .bc 文件失败: {}", e))?;

    Ok(())
}
