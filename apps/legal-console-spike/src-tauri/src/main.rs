mod dummy;
mod intake;
mod run;
mod status;

fn main() {
    tauri::Builder::default()
        .plugin(
            tauri_plugin_opener::Builder::new()
                .open_js_links_on_click(false)
                .build(),
        )
        .invoke_handler(tauri::generate_handler![
            dummy::create_synthetic_test_file,
            intake::open_intake_folder,
            run::run_synthetic_dry_run,
            status::get_status_snapshot
        ])
        .run(tauri::generate_context!())
        .expect("failed to run OpenClaw Legal console prototype");
}
