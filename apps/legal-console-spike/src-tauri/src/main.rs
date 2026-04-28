mod status;

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![status::get_status_snapshot])
        .run(tauri::generate_context!())
        .expect("failed to run OpenClaw Legal console prototype");
}
