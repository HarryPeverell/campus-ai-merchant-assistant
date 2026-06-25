"""OpenAI 兼容文本请求。"""
import json
import requests


class AIError(RuntimeError):
    pass


def configured(settings):
    return bool(settings.get("base_url") and settings.get("api_key") and settings.get("model"))


def complete(settings, prompt, system="你是可靠的中文校园商圈运营助手。", stream=False, on_delta=None):
    if not configured(settings):
        raise AIError("尚未配置 AI API。")
    payload = {
        "model": settings["model"],
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "temperature": float(settings.get("temperature", 0.7)),
        "max_tokens": int(settings.get("max_tokens", 2000)), "stream": stream,
    }
    try:
        response = requests.post(
            str(settings["base_url"]).rstrip("/") + "/chat/completions", json=payload,
            headers={"Authorization": "Bearer " + str(settings["api_key"]), "Content-Type": "application/json"},
            timeout=(10, 90), stream=stream,
        )
        if not response.ok:
            try:
                message = response.json().get("error", {}).get("message", response.text)
            except ValueError:
                message = response.text
            raise AIError("AI 接口返回 {}：{}".format(response.status_code, message[:300]))
        if not stream:
            return str(response.json()["choices"][0]["message"]["content"]).strip()
        parts = []
        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if raw == "[DONE]":
                break
            try:
                delta = json.loads(raw)["choices"][0].get("delta", {}).get("content", "")
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if delta:
                parts.append(delta)
                if on_delta:
                    on_delta(delta)
        return "".join(parts).strip()
    except requests.RequestException as exc:
        raise AIError("无法连接 AI 接口：{}".format(exc))
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError("AI 接口响应格式不兼容：{}".format(exc))
