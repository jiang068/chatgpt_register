"""并发/批量任务模块（低耦合）：
实现 _register_one 与 run_batch，但对 `chatgpt_register` 做延迟导入以避免循环依赖。
"""
import importlib
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed


def _register_one(idx, total, proxy, output_file):
    """单个注册任务（在线程中运行）。对主模块做延迟导入以避免循环导入问题。
    返回 (ok, email, error_message)
    """
    try:
        mod = importlib.import_module("chatgpt_register")
        ChatGPTRegister = getattr(mod, "ChatGPTRegister")
        _generate_password = getattr(mod, "_generate_password")
        _random_name = getattr(mod, "_random_name")
        _random_birthdate = getattr(mod, "_random_birthdate")
        _print_lock = getattr(mod, "_print_lock")
        _file_lock = getattr(mod, "_file_lock")

        reg = ChatGPTRegister(proxy=proxy, tag=f"{idx}")

        # 创建临时邮箱（freemail）
        reg._print("[freemail] 创建临时邮箱...")
        email, email_pwd, mail_token = reg.create_temp_email()
        tag = email.split("@")[0]
        reg.tag = tag

        chatgpt_password = _generate_password()
        name = _random_name()
        birthdate = _random_birthdate()

        with _print_lock:
            print(f"\n{'='*60}")
            print(f"  [{idx}/{total}] 注册: {email}")
            print(f"  ChatGPT密码: {chatgpt_password}")
            print(f"  邮箱密码: {email_pwd}")
            print(f"  姓名: {name} | 生日: {birthdate}")
            print(f"{'='*60}")

        reg.run_register(email, chatgpt_password, name, birthdate, mail_token)

        oauth_ok = True
        mod = importlib.import_module("chatgpt_register")
        ENABLE_OAUTH = getattr(mod, "ENABLE_OAUTH", True)
        if ENABLE_OAUTH:
            reg._print("[OAuth] 开始获取 Codex Token...")
            tokens = reg.perform_codex_oauth_login_http(email, chatgpt_password, mail_token=mail_token)
            oauth_ok = bool(tokens and tokens.get("access_token"))
            if oauth_ok:
                save_fn = getattr(mod, "_save_codex_tokens", None)
                if save_fn:
                    save_fn(email, tokens)

        with _file_lock:
            with open(output_file, "a", encoding="utf-8") as out:
                out.write(f"{email}----{chatgpt_password}----{email_pwd}----oauth={'ok' if oauth_ok else 'fail'}\n")

        with _print_lock:
            print(f"\n[OK] [{tag}] {email} 注册成功!")
        return True, email, None

    except Exception as e:
        try:
            mod = importlib.import_module("chatgpt_register")
            _print_lock = getattr(mod, "_print_lock")
        except Exception:
            _print_lock = None
        error_msg = str(e)
        if _print_lock:
            with _print_lock:
                print(f"\n[FAIL] [{idx}] 注册失败: {error_msg}")
                traceback.print_exc()
        else:
            print(f"[FAIL] [{idx}] 注册失败: {error_msg}")
            traceback.print_exc()
        return False, None, error_msg


def run_batch(total_accounts: int = 3, output_file="registered_accounts.txt",
              max_workers: int = 3, proxy: str = None):
    """并发批量注册 - freemail 临时邮箱版（从 app 运行）
    使用延迟导入读取配置以保持与现有模块兼容。
    """
    mod = importlib.import_module("chatgpt_register")
    FREEMAIL_WORKER_DOMAIN = getattr(mod, "FREEMAIL_WORKER_DOMAIN", "")
    ENABLE_OAUTH = getattr(mod, "ENABLE_OAUTH", True)
    OAUTH_ISSUER = getattr(mod, "OAUTH_ISSUER", "")
    OAUTH_CLIENT_ID = getattr(mod, "OAUTH_CLIENT_ID", "")
    TOKEN_JSON_DIR = getattr(mod, "TOKEN_JSON_DIR", "")
    AK_FILE = getattr(mod, "AK_FILE", "")
    RK_FILE = getattr(mod, "RK_FILE", "")

    actual_workers = min(max_workers, total_accounts)
    print(f"\n{'#'*60}")
    print(f"  ChatGPT 批量自动注册 (freemail 临时邮箱版)")
    print(f"  注册数量: {total_accounts} | 并发数: {actual_workers}")
    print(f"  freemail worker: {FREEMAIL_WORKER_DOMAIN}")
    print(f"  OAuth: {'开启' if ENABLE_OAUTH else '关闭'}")
    if ENABLE_OAUTH:
        print(f"  OAuth Issuer: {OAUTH_ISSUER}")
        print(f"  OAuth Client: {OAUTH_CLIENT_ID}")
        print(f"  Token输出: {TOKEN_JSON_DIR}/, {AK_FILE}, {RK_FILE}")
    print(f"  输出文件: {output_file}")
    print(f"{'#'*60}\n")

    success_count = 0
    fail_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = {}
        for idx in range(1, total_accounts + 1):
            future = executor.submit(_register_one, idx, total_accounts, proxy, output_file)
            futures[future] = idx

        for future in as_completed(futures):
            idx = futures[future]
            try:
                ok, email, err = future.result()
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
                    print(f"  [账号 {idx}] 失败: {err}")
            except Exception as e:
                fail_count += 1
                print(f"[FAIL] 账号 {idx} 线程异常: {e}")

    elapsed = time.time() - start_time
    avg = elapsed / total_accounts if total_accounts else 0
    print(f"\n{'#'*60}")
    print(f"  注册完成! 耗时 {elapsed:.1f} 秒")
    print(f"  总数: {total_accounts} | 成功: {success_count} | 失败: {fail_count}")
    print(f"  平均速度: {avg:.1f} 秒/个")
    if success_count > 0:
        print(f"  结果文件: {output_file}")
    print(f"{'#'*60}")
