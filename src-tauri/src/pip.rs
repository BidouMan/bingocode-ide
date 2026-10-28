//! pip 包管理命令：列表/安装/卸载/版本/升级。

use serde::{Deserialize, Serialize};
use crate::hidden_command;
use crate::python_env::resolve_engine_env;

#[derive(Debug, Serialize, Deserialize)]
pub(crate) struct PipPackage {
    pub name: String,
    pub version: String,
}

/// 获取 venv 中已安装的包列表
#[tauri::command]
pub(crate) fn pip_list_installed(app: tauri::AppHandle) -> Result<Vec<PipPackage>, String> {
    let python_path = find_venv_python(&app)?;
    let output = hidden_command(&python_path)
        .args(["-m", "pip", "list", "--format=json", "--not-required"])
        .output()
        .map_err(|e| format!("执行 pip list 失败: {}", e))?;

    if !output.status.success() {
        // --not-required 可能在旧版 pip 不支持，回退到不带该参数
        let output2 = hidden_command(&python_path)
            .args(["-m", "pip", "list", "--format=json"])
            .output()
            .map_err(|e| format!("执行 pip list 失败: {}", e))?;
        let stdout = String::from_utf8_lossy(&output2.stdout).to_string();
        return parse_pip_list(&stdout);
    }

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    parse_pip_list(&stdout)
}

/// 获取 venv 中所有已安装包（含依赖）
#[tauri::command]
pub(crate) fn pip_list_all(app: tauri::AppHandle) -> Result<Vec<PipPackage>, String> {
    let python_path = find_venv_python(&app)?;
    let output = hidden_command(&python_path)
        .args(["-m", "pip", "list", "--format=json"])
        .output()
        .map_err(|e| format!("执行 pip list 失败: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    parse_pip_list(&stdout)
}

fn parse_pip_list(json_str: &str) -> Result<Vec<PipPackage>, String> {
    let parsed: serde_json::Value = serde_json::from_str(json_str)
        .map_err(|e| format!("解析 pip list 输出失败: {}", e))?;

    let arr = parsed.as_array().ok_or("pip list 输出格式错误")?;
    let mut packages = Vec::new();
    for item in arr {
        if let (Some(name), Some(version)) = (item["name"].as_str(), item["version"].as_str()) {
            packages.push(PipPackage {
                name: name.to_string(),
                version: version.to_string(),
            });
        }
    }
    Ok(packages)
}

/// 安装包到 venv
#[tauri::command]
pub(crate) fn pip_install_package(
    app: tauri::AppHandle,
    package: String,
    version: Option<String>,
    mirror: String,
) -> Result<String, String> {
    let python_path = find_venv_python(&app)?;
    let spec = match version {
        Some(v) => format!("{}=={}", package, v),
        None => package,
    };

    let output = hidden_command(&python_path)
        .args([
            "-m", "pip", "install",
            &spec,
            "-i", &mirror,
            "--no-warn-script-location",
        ])
        .output()
        .map_err(|e| format!("执行 pip install 失败: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Err(format!("安装失败:\n{}", stderr));
    }

    Ok(stdout)
}

/// 卸载 venv 中的包
#[tauri::command]
pub(crate) fn pip_uninstall_package(
    app: tauri::AppHandle,
    package: String,
) -> Result<String, String> {
    let python_path = find_venv_python(&app)?;
    let output = hidden_command(&python_path)
        .args(["-m", "pip", "uninstall", &package, "-y"])
        .output()
        .map_err(|e| format!("执行 pip uninstall 失败: {}", e))?;

    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if !output.status.success() {
        return Err(format!("卸载失败:\n{}", stderr));
    }

    Ok(format!("已卸载 {}", package))
}

/// 获取指定包在 PyPI 上的可用版本
#[tauri::command]
pub(crate) fn pip_get_versions(
    package: String,
) -> Result<Vec<String>, String> {
    // 使用 PyPI JSON API 查询可用版本
    let url = format!("https://pypi.org/pypi/{}/json", package);
    let output = hidden_command("curl")
        .args(["-s", "--max-time", "10", &url])
        .output()
        .map_err(|e| format!("查询版本失败: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    if stdout.is_empty() {
        return Err(format!("无法获取 {} 的版本信息", package));
    }

    let parsed: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|e| format!("解析版本信息失败: {}", e))?;

    let releases = parsed["releases"].as_object()
        .ok_or("版本信息格式错误")?;

    let mut versions: Vec<String> = releases.keys().cloned().collect();
    versions.sort_by(|a, b| {
        // 简单的版本倒序排列（最新的在前）
        b.cmp(a)
    });

    Ok(versions)
}

fn find_venv_python(app: &tauri::AppHandle) -> Result<String, String> {
    let env = resolve_engine_env(
        app.clone(),
        String::new(),
        None,
    )?;
    Ok(env.python_path)
}

#[derive(Debug, Serialize, Deserialize)]
pub(crate) struct OutdatedPackage {
    pub name: String,
    pub current_version: String,
    pub latest_version: String,
}

/// 检查所有可更新的包
#[tauri::command]
pub(crate) fn pip_check_outdated(app: tauri::AppHandle) -> Result<Vec<OutdatedPackage>, String> {
    let python_path = find_venv_python(&app)?;
    let output = hidden_command(&python_path)
        .args(["-m", "pip", "list", "--outdated", "--format=json"])
        .output()
        .map_err(|e| format!("检查更新失败: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let parsed: serde_json::Value = serde_json::from_str(&stdout)
        .map_err(|e| format!("解析更新信息失败: {}", e))?;

    let arr = parsed.as_array().ok_or("更新信息格式错误")?;
    let mut packages = Vec::new();
    for item in arr {
        if let (Some(name), Some(ver), Some(latest)) = (
            item["name"].as_str(),
            item["version"].as_str(),
            item["latest_version"].as_str(),
        ) {
            packages.push(OutdatedPackage {
                name: name.to_string(),
                current_version: ver.to_string(),
                latest_version: latest.to_string(),
            });
        }
    }
    Ok(packages)
}

/// 升级单个包
#[tauri::command]
pub(crate) fn pip_upgrade_package(
    app: tauri::AppHandle,
    package: String,
    mirror: String,
) -> Result<String, String> {
    let python_path = find_venv_python(&app)?;
    let output = hidden_command(&python_path)
        .args([
            "-m", "pip", "install", "--upgrade", &package,
            "-i", &mirror,
            "--no-warn-script-location",
        ])
        .output()
        .map_err(|e| format!("升级包失败: {}", e))?;

    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    if !output.status.success() {
        return Err(format!("升级失败:\n{}", stderr));
    }
    Ok(format!("{} 已升级", package))
}
