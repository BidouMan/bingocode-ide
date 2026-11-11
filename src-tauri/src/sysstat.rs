//! 进程资源统计：按进程树汇总 BingoCode 自身占用（主进程 + WebView2 子进程 + Python 引擎）。
//!
//! 为什么按进程树：Windows 上 WebView2 的渲染/GPU 进程由系统共享运行时拉起，
//! 在任务管理器里会和其他 WebView2 应用（Edge、Teams…）混在一起，无法按应用分组。
//! 唯一可靠的归属关系是父子关系——`msedgewebview2.exe` 的父进程就是本应用主进程。
//! macOS 的 WebKit WebContent/GPU 子进程同理。

use serde::Serialize;
use std::collections::HashMap;
use std::sync::Mutex;
use sysinfo::{Pid, ProcessRefreshKind, ProcessesToUpdate, System};

pub struct SysStatState {
    /// 常驻的 System：CPU 占用率是两次采样之间的差值，必须复用同一个实例才能算准
    pub system: Mutex<System>,
}

impl SysStatState {
    pub fn new() -> Self {
        Self {
            system: Mutex::new(System::new()),
        }
    }
}

#[derive(Clone, Serialize, Default)]
pub struct ProcessGroup {
    /// 分组标识：main / webview / python / other
    pub kind: String,
    /// 相对整机 CPU（0-100），已按逻辑核心数归一化
    pub cpu: f32,
    /// 内存（字节）
    pub memory: u64,
}

#[derive(Clone, Serialize, Default)]
pub struct AppResourceStats {
    pub total_memory: u64,
    pub total_cpu: f32,
    pub process_count: usize,
    pub groups: Vec<ProcessGroup>,
}

/// 按进程名归类：渲染进程 / Python 引擎 / 其它
fn classify(name: &str) -> &'static str {
    let lower = name.to_ascii_lowercase();
    if lower.contains("msedgewebview2") || lower.contains("webkit") || lower.contains("crashepad") {
        "webview"
    } else if lower.starts_with("python") {
        "python"
    } else {
        "other"
    }
}

#[tauri::command]
pub fn get_app_resource_stats(
    state: tauri::State<'_, SysStatState>,
) -> Result<AppResourceStats, String> {
    let mut sys = state.system.lock().map_err(|e| e.to_string())?;

    let refresh = ProcessRefreshKind::nothing().with_cpu().with_memory();
    sys.refresh_processes_specifics(ProcessesToUpdate::All, true, refresh);

    let cores = std::thread::available_parallelism()
        .map(|n| n.get() as f32)
        .unwrap_or(1.0);

    let self_pid = Pid::from_u32(std::process::id());

    // 父 → 子索引，再从本进程出发 BFS 收集整棵子树
    let mut children: HashMap<Pid, Vec<Pid>> = HashMap::new();
    for (pid, proc_entry) in sys.processes() {
        if let Some(parent) = proc_entry.parent() {
            children.entry(parent).or_default().push(*pid);
        }
    }

    let mut members: Vec<Pid> = vec![self_pid];
    let mut queue: Vec<Pid> = vec![self_pid];
    while let Some(pid) = queue.pop() {
        if let Some(kids) = children.get(&pid) {
            for kid in kids {
                if members.contains(kid) {
                    continue;
                }
                members.push(*kid);
                queue.push(*kid);
            }
        }
    }

    let mut stats = AppResourceStats::default();
    let mut buckets: HashMap<&'static str, ProcessGroup> = HashMap::new();

    for pid in &members {
        let Some(proc_entry) = sys.process(*pid) else {
            continue;
        };
        let kind = if *pid == self_pid {
            "main"
        } else {
            classify(&proc_entry.name().to_string_lossy())
        };

        let cpu = proc_entry.cpu_usage() / cores;
        let memory = proc_entry.memory();

        stats.total_cpu += cpu;
        stats.total_memory += memory;
        stats.process_count += 1;

        let entry = buckets.entry(kind).or_insert_with(|| ProcessGroup {
            kind: kind.to_string(),
            ..Default::default()
        });
        entry.cpu += cpu;
        entry.memory += memory;
    }

    let mut groups: Vec<ProcessGroup> = buckets.into_values().collect();
    groups.sort_by(|a, b| b.memory.cmp(&a.memory));
    stats.groups = groups;

    Ok(stats)
}
