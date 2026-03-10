#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.io import to_html
import yfinance as yf


KST = ZoneInfo("Asia/Seoul")


def _now_kst() -> dt.datetime:
    return dt.datetime.now(tz=KST)


def _safe_num(value: float | int | np.number | None) -> float:
    if value is None:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _fmt_price(value: float) -> str:
    if np.isnan(value):
        return "N/A"
    return f"${value:,.2f}"


def _fmt_pct(value: float) -> str:
    if np.isnan(value):
        return "N/A"
    return f"{value:.2f}%"


def _fmt_ratio(value: float) -> str:
    if np.isnan(value):
        return "N/A"
    return f"{value:.2f}"


def _fmt_delta(value: float) -> str:
    if np.isnan(value):
        return "N/A"
    return f"{value:+.2f}"


def _calculate_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=window, min_periods=window).mean()
    avg_loss = loss.rolling(window=window, min_periods=window).mean()
    rs = avg_gain / (avg_loss + 1e-9)
    return 100 - (100 / (1 + rs))


def _calculate_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    return macd, macd_signal, macd - macd_signal


def _calculate_anchored_vwap(df: pd.DataFrame, anchor_idx: pd.Timestamp) -> pd.Series:
    if df.empty or anchor_idx is None:
        return pd.Series(np.nan, index=df.index)
    anchor_mask = df.index >= anchor_idx
    if not anchor_mask.any():
        return pd.Series(np.nan, index=df.index)

    ref = df.loc[anchor_mask]
    typical_price = (ref["High"] + ref["Low"] + ref["Close"]) / 3
    v_p = typical_price * ref["Volume"]
    avwap = v_p.cumsum() / (ref["Volume"].cumsum() + 1e-9)
    full = pd.Series(np.nan, index=df.index)
    full.loc[anchor_mask] = avwap
    return full


def _calculate_volume_profile_poc(df: pd.DataFrame, bins: int = 40) -> float:
    if df.empty:
        return float("nan")
    p_min = _safe_num(df["Low"].min())
    p_max = _safe_num(df["High"].max())
    if np.isnan(p_min) or np.isnan(p_max) or p_min == p_max:
        return p_min

    edges = np.linspace(p_min, p_max, bins + 1)
    cut = pd.cut(df["Close"], bins=edges, include_lowest=True)
    vprofile = df.groupby(cut, observed=False)["Volume"].sum()
    if vprofile.empty:
        return float("nan")
    i = int(np.argmax(vprofile.values))
    return float((edges[i] + edges[i + 1]) / 2)


def _get_past_row(df: pd.DataFrame, trading_days: int) -> pd.Series:
    idx = -1 - trading_days
    if len(df) + idx >= 0:
        return df.iloc[idx]
    return df.iloc[0]


def _check_divergence(df: pd.DataFrame, window: int = 20) -> str:
    if len(df) < window + 1:
        return "None"
    cp, pp = _safe_num(df["Close"].iloc[-1]), _safe_num(df["Close"].iloc[-window])
    cr, pr = _safe_num(df["RSI"].iloc[-1]), _safe_num(df["RSI"].iloc[-window])
    if any(np.isnan(v) for v in [cp, pp, cr, pr]):
        return "None"
    if cp > pp and cr < pr:
        return "BEARISH (P↑ R↓)"
    if cp < pp and cr > pr:
        return "BULLISH (P↓ R↑)"
    return "None"


def _analyze_smc_amd_flow(df: pd.DataFrame) -> dict[str, object]:
    if len(df) < 30:
        false_ser = pd.Series(False, index=df.index)
        return {
            "sweep_high_ser": false_ser,
            "sweep_low_ser": false_ser,
            "sweep_high": False,
            "sweep_low": False,
            "order_flow": "Unknown",
            "amd_phase": "Unknown",
        }

    lookback = 20
    prev_high = df["High"].shift(1).rolling(window=lookback, min_periods=lookback).max()
    prev_low = df["Low"].shift(1).rolling(window=lookback, min_periods=lookback).min()
    sweep_high = (df["High"] > prev_high) & (df["Close"] < prev_high)
    sweep_low = (df["Low"] < prev_low) & (df["Close"] > prev_low)

    flow_delta = (df["Close"] - df["Open"]) * df["Volume"]
    flow_mean = _safe_num(flow_delta.tail(5).mean())
    order_flow = "Bullish" if flow_mean > 0 else "Bearish"

    atr = df["ATR14"]
    atr_ref = _safe_num(atr.rolling(20, min_periods=5).mean().iloc[-1])
    atr_now = _safe_num(atr.iloc[-1])
    is_acc = False if np.isnan(atr_ref) or np.isnan(atr_now) else atr_now < atr_ref
    amd_phase = "Accumulation" if is_acc else "Distribution/Trend"

    return {
        "sweep_high_ser": sweep_high.fillna(False),
        "sweep_low_ser": sweep_low.fillna(False),
        "sweep_high": bool(sweep_high.fillna(False).iloc[-1]),
        "sweep_low": bool(sweep_low.fillna(False).iloc[-1]),
        "order_flow": order_flow,
        "amd_phase": amd_phase,
    }


def _analyze_macro(df_qqq: pd.DataFrame, lookback: int = 60) -> dict[str, float | str] | None:
    try:
        macro_tickers = ["^TNX", "SPY", "^VIX", "DX-Y.NYB", "SOXX"]
        raw = yf.download(macro_tickers, period="2y", progress=False, auto_adjust=True)
        if raw.empty:
            return None
        macro_data = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
        if isinstance(macro_data.columns, pd.MultiIndex):
            macro_data.columns = macro_data.columns.get_level_values(0)

        combined = pd.concat([df_qqq["Close"], macro_data], axis=1, sort=False).ffill().dropna()
        combined.columns = ["QQQ"] + list(macro_data.columns)
        if len(combined) < max(lookback + 5, 40):
            return None

        pct = combined.pct_change()
        yield_corr = _safe_num(pct["QQQ"].rolling(lookback).corr(pct["^TNX"]).iloc[-1])
        dxy_corr = _safe_num(pct["QQQ"].rolling(lookback).corr(pct["DX-Y.NYB"]).iloc[-1])
        soxx_corr = _safe_num(pct["QQQ"].rolling(lookback).corr(pct["SOXX"]).iloc[-1])
        rs_slope = _safe_num((combined["QQQ"] / combined["SPY"]).pct_change(20).iloc[-1] * 100)
        vix_curr = _safe_num(combined["^VIX"].iloc[-1])

        return {
            "yield_corr": yield_corr,
            "yield_10y": _safe_num(combined["^TNX"].iloc[-1]),
            "dxy_corr": dxy_corr,
            "dollar_idx": _safe_num(combined["DX-Y.NYB"].iloc[-1]),
            "soxx_corr": soxx_corr,
            "vix_curr": vix_curr,
            "vix_status": "CALM" if vix_curr < 20 else "FEAR",
            "rs_slope_20d": rs_slope,
        }
    except Exception:
        return None


def _compute_composite_score(
    curr: pd.Series, macro: dict[str, float | str] | None, smc: dict[str, object]
) -> float:
    rsi = _safe_num(curr.get("RSI"))
    bbw = _safe_num(curr.get("BB_Width"))
    trend_strength = _safe_num(curr.get("TREND_STRENGTH"))

    rsi_s = 50 - abs(rsi - 50) if not np.isnan(rsi) else 0
    bw_score = max(0, 20 - bbw) if not np.isnan(bbw) else 0
    trend_score = np.tanh((0 if np.isnan(trend_strength) else trend_strength) / 10) * 20
    tech_score = rsi_s * 0.3 + bw_score * 0.2 + trend_score

    if macro is None:
        base = tech_score + 30
    else:
        macro_bonus = 10 if macro.get("vix_status") == "CALM" else -10
        dxy_bonus = 5 if _safe_num(macro.get("dxy_corr")) < 0 else -5
        base = tech_score + macro_bonus + dxy_bonus + 30

    smc_bonus = 5 if smc.get("sweep_low") else (-5 if smc.get("sweep_high") else 0)
    return float(np.clip(base + smc_bonus, 0, 100))


def _prepare_price_data(period: str) -> pd.DataFrame:
    df = yf.download("QQQ", period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        raise RuntimeError("QQQ 가격 데이터를 가져오지 못했습니다.")

    out = df.copy()
    out["MA200"] = out["Close"].rolling(200, min_periods=50).mean()
    out["MA50"] = out["Close"].rolling(50, min_periods=20).mean()
    out["MA20"] = out["Close"].rolling(20, min_periods=20).mean()
    out["STD20"] = out["Close"].rolling(20, min_periods=20).std()
    out["BB_Upper"] = out["MA20"] + out["STD20"] * 2
    out["BB_Lower"] = out["MA20"] - out["STD20"] * 2
    out["BB_Width"] = (out["BB_Upper"] - out["BB_Lower"]) / (out["MA20"] + 1e-9) * 100
    out["Avg_Vol"] = out["Volume"].rolling(20, min_periods=5).mean()
    out["RET_1D"] = out["Close"].pct_change(1) * 100
    out["RET_5D"] = out["Close"].pct_change(5) * 100
    out["RET_1M"] = out["Close"].pct_change(21) * 100

    tr = pd.concat(
        [
            out["High"] - out["Low"],
            (out["High"] - out["Close"].shift()).abs(),
            (out["Low"] - out["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["ATR14"] = tr.rolling(14).mean()
    out["RV20"] = out["Close"].pct_change().rolling(20).std() * np.sqrt(252) * 100
    out["RSI"] = _calculate_rsi(out["Close"])
    out["MACD"], out["MACD_SIGNAL"], out["MACD_HIST"] = _calculate_macd(out["Close"])
    out["TREND_STRENGTH"] = (out["MA50"] - out["MA200"]).abs() / (out["ATR14"] + 1e-9)
    out["Rolling_Ret"] = out["Close"].pct_change(20) * 100

    anchor_lookback = out["Low"].tail(min(120, len(out)))
    anchor_idx = anchor_lookback.idxmin() if not anchor_lookback.empty else out.index[0]
    out["AVWAP"] = _calculate_anchored_vwap(out, anchor_idx)
    return out


def _fetch_option_data(max_exp: int, strike_band: float) -> tuple[pd.DataFrame, list[str], float]:
    ticker = yf.Ticker("QQQ")
    expiries = list(ticker.options[:max_exp])
    if not expiries:
        raise RuntimeError("QQQ 옵션 만기 정보를 가져오지 못했습니다.")

    hist = ticker.history(period="5d", auto_adjust=False)
    if hist.empty:
        raise RuntimeError("QQQ 최근 종가를 가져오지 못했습니다.")
    last_close = float(hist["Close"].iloc[-1])

    frames: list[pd.DataFrame] = []
    for exp in expiries:
        oc = ticker.option_chain(exp)
        exp_date = dt.datetime.strptime(exp, "%Y-%m-%d").date()
        dte = (exp_date - _now_kst().date()).days

        for opt_type, src in (("call", oc.calls), ("put", oc.puts)):
            if src is None or src.empty:
                continue
            d = src.copy()
            d["type"] = opt_type
            d["expiry"] = exp
            d["dte"] = dte
            frames.append(d)

    if not frames:
        raise RuntimeError("옵션체인 데이터가 비어 있습니다.")

    all_opt = pd.concat(frames, ignore_index=True)
    for col in ["strike", "openInterest", "volume", "impliedVolatility", "lastPrice", "bid", "ask"]:
        if col in all_opt.columns:
            all_opt[col] = pd.to_numeric(all_opt[col], errors="coerce")

    all_opt = all_opt.dropna(subset=["strike", "impliedVolatility"]).copy()
    all_opt = all_opt[all_opt["impliedVolatility"] > 0]
    all_opt = all_opt[
        all_opt["strike"].between(last_close * (1.0 - strike_band), last_close * (1.0 + strike_band))
    ].copy()
    if all_opt.empty:
        raise RuntimeError("설정한 스트라이크 범위 내 옵션 데이터가 없습니다.")
    return all_opt, expiries, last_close


def _compute_max_pain(df_opt: pd.DataFrame) -> float:
    strikes = np.sort(df_opt["strike"].dropna().unique())
    if len(strikes) == 0:
        return float("nan")

    calls = df_opt[df_opt["type"] == "call"][["strike", "openInterest"]].copy()
    puts = df_opt[df_opt["type"] == "put"][["strike", "openInterest"]].copy()
    calls["openInterest"] = calls["openInterest"].fillna(0)
    puts["openInterest"] = puts["openInterest"].fillna(0)

    losses = []
    for s in strikes:
        c_loss = ((s - calls["strike"]).clip(lower=0) * calls["openInterest"]).sum()
        p_loss = ((puts["strike"] - s).clip(lower=0) * puts["openInterest"]).sum()
        losses.append((s, c_loss + p_loss))
    if not losses:
        return float("nan")
    return float(min(losses, key=lambda x: x[1])[0])


def _compute_term_structure(df_opt: pd.DataFrame, spot: float) -> pd.DataFrame:
    rows = []
    for exp, grp in df_opt.groupby("expiry", sort=True):
        calls = grp[grp["type"] == "call"].copy()
        puts = grp[grp["type"] == "put"].copy()
        if calls.empty or puts.empty:
            continue
        c = calls.iloc[(calls["strike"] - spot).abs().argmin()]
        p = puts.iloc[(puts["strike"] - spot).abs().argmin()]
        atm_iv = np.nanmean([_safe_num(c["impliedVolatility"]), _safe_num(p["impliedVolatility"])]) * 100
        rows.append({"expiry": exp, "dte": int(c["dte"]), "atm_iv": float(atm_iv)})
    out = pd.DataFrame(rows).sort_values(["dte", "expiry"])
    return out


def _build_price_figure(df: pd.DataFrame) -> go.Figure:
    view = df.tail(120).copy()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=view.index, y=view["Close"], mode="lines", name="QQQ Close", line=dict(color="#111827", width=2))
    )
    fig.add_trace(
        go.Scatter(x=view.index, y=view["MA20"], mode="lines", name="MA20", line=dict(color="#2563EB", width=1.5))
    )
    fig.add_trace(
        go.Scatter(x=view.index, y=view["MA50"], mode="lines", name="MA50", line=dict(color="#DC2626", width=1.5))
    )
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=view["MA200"],
            mode="lines",
            name="MA200",
            line=dict(color="#059669", width=1.7, dash="dot"),
        )
    )
    fig.update_layout(
        title="QQQ 가격 추이 (최근 120거래일)",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _build_volume_figure(df: pd.DataFrame) -> go.Figure:
    view = df.tail(120).copy()
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=view.index,
            y=view["Volume"],
            name="Volume",
            marker_color="#d1d5db",
            opacity=0.65,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=view["Avg_Vol"],
            mode="lines",
            name="20D Avg Volume",
            line=dict(color="#2563EB", width=2),
        )
    )
    fig.update_layout(
        title="거래량 추이",
        xaxis_title="Date",
        yaxis_title="Volume",
        template="plotly_white",
        height=340,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _build_macd_figure(df: pd.DataFrame) -> go.Figure:
    view = df.tail(120).copy()
    colors = np.where(view["MACD_HIST"] >= 0, "#ef4444", "#3b82f6")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=view.index,
            y=view["MACD_HIST"],
            name="MACD Hist",
            marker_color=colors,
            opacity=0.7,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=view["MACD"],
            mode="lines",
            name="MACD",
            line=dict(color="#1d4ed8", width=2),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=view["MACD_SIGNAL"],
            mode="lines",
            name="Signal",
            line=dict(color="#f59e0b", width=1.5),
        )
    )
    fig.update_layout(
        title="MACD",
        xaxis_title="Date",
        yaxis_title="MACD",
        template="plotly_white",
        height=340,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _build_oi_figure(df_opt: pd.DataFrame, nearest_expiry: str) -> go.Figure:
    near = df_opt[df_opt["expiry"] == nearest_expiry].copy()
    call = near[near["type"] == "call"].groupby("strike", as_index=False)["openInterest"].sum()
    put = near[near["type"] == "put"].groupby("strike", as_index=False)["openInterest"].sum()

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=call["strike"],
            y=call["openInterest"],
            name=f"Call OI ({nearest_expiry})",
            marker_color="#2563EB",
            opacity=0.75,
        )
    )
    fig.add_trace(
        go.Bar(
            x=put["strike"],
            y=put["openInterest"],
            name=f"Put OI ({nearest_expiry})",
            marker_color="#DC2626",
            opacity=0.65,
        )
    )
    fig.update_layout(
        barmode="overlay",
        title=f"최근 만기 OI 분포 ({nearest_expiry})",
        xaxis_title="Strike",
        yaxis_title="Open Interest",
        template="plotly_white",
        height=420,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _build_term_structure_figure(term_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=term_df["dte"],
            y=term_df["atm_iv"],
            mode="lines+markers+text",
            text=term_df["expiry"],
            textposition="top center",
            name="ATM IV",
            line=dict(color="#7C3AED", width=2),
            marker=dict(size=8),
        )
    )
    fig.update_layout(
        title="ATM IV 만기 구조",
        xaxis_title="Days to Expiry (DTE)",
        yaxis_title="ATM IV (%)",
        template="plotly_white",
        height=420,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _build_surface_figure(df_opt: pd.DataFrame) -> go.Figure:
    surf = df_opt[["strike", "dte", "impliedVolatility", "type"]].dropna().copy()
    surf["iv_pct"] = surf["impliedVolatility"] * 100
    surf = (
        surf.groupby(["dte", "strike"], as_index=False)["iv_pct"]
        .mean()
        .sort_values(["dte", "strike"])
        .reset_index(drop=True)
    )

    grid = surf.pivot(index="dte", columns="strike", values="iv_pct").sort_index().sort_index(axis=1)
    # 시장 데이터는 결측이 흔하므로 strike 축, dte 축 순서로 보간해 표면을 만든다.
    grid = grid.interpolate(axis=1, limit_direction="both")
    grid = grid.interpolate(axis=0, limit_direction="both")
    if grid.isna().values.any():
        mean_iv = float(np.nanmean(grid.values))
        if np.isnan(mean_iv):
            mean_iv = float(np.nanmean(surf["iv_pct"].values))
        grid = grid.fillna(mean_iv)

    fig = go.Figure()
    fig.add_trace(
        go.Surface(
            x=grid.columns.astype(float),
            y=grid.index.astype(float),
            z=grid.values,
            colorscale="Viridis",
            opacity=0.9,
            colorbar=dict(title="IV(%)"),
            contours=dict(z=dict(show=True, usecolormap=True, project_z=True)),
            hovertemplate="Strike=%{x:.2f}<br>DTE=%{y}<br>IV=%{z:.2f}%<extra></extra>",
            name="IV Surface",
        )
    )
    fig.add_trace(
        go.Scatter3d(
            x=surf["strike"],
            y=surf["dte"],
            z=surf["iv_pct"],
            mode="markers",
            marker=dict(size=2.5, color="#111827", opacity=0.45),
            hovertemplate="Raw Point<br>Strike=%{x:.2f}<br>DTE=%{y}<br>IV=%{z:.2f}%<extra></extra>",
            name="Raw IV Points",
        )
    )
    fig.update_layout(
        title="QQQ IV Surface (3D Surface)",
        scene=dict(
            xaxis_title="Strike",
            yaxis_title="DTE",
            zaxis_title="IV (%)",
            bgcolor="#F8FAFC",
        ),
        template="plotly_white",
        height=520,
        margin=dict(l=0, r=0, t=60, b=0),
    )
    return fig


def _build_conclusion(
    spot: float,
    max_pain: float,
    pcr_oi: float,
    pcr_vol: float,
    term_df: pd.DataFrame,
    recent_atr: float,
) -> list[str]:
    lines: list[str] = []

    if not np.isnan(max_pain):
        gap_pct = (spot / max_pain - 1) * 100
        if abs(gap_pct) < 1.0:
            lines.append("현물 가격이 Max Pain 부근에 있어 만기 전 가격 고정(핀) 압력이 생길 수 있습니다.")
        elif gap_pct > 0:
            lines.append("현물 가격이 Max Pain 위에 있어 단기 되돌림 압력 가능성을 열어둬야 합니다.")
        else:
            lines.append("현물 가격이 Max Pain 아래에 있어 상방 회귀 시도 가능성을 함께 점검해야 합니다.")

    if not np.isnan(pcr_oi):
        if pcr_oi > 1.15:
            lines.append("OI 기준 Put/Call 비율이 높아 하방 헤지 수요가 우세합니다.")
        elif pcr_oi < 0.85:
            lines.append("OI 기준 Call 비중이 상대적으로 높아 상방 베팅 심리가 우세합니다.")
        else:
            lines.append("OI 기준 Put/Call 비율은 중립권으로 과도한 한쪽 쏠림은 제한적입니다.")

    if not term_df.empty:
        short_iv = _safe_num(term_df.iloc[0]["atm_iv"])
        long_iv = _safe_num(term_df.iloc[-1]["atm_iv"])
        if not np.isnan(short_iv) and not np.isnan(long_iv):
            if short_iv > long_iv + 1.0:
                lines.append("단기 ATM IV가 장기보다 높아 이벤트성 단기 리스크가 크게 반영된 구조입니다.")
            elif long_iv > short_iv + 1.0:
                lines.append("장기 ATM IV 프리미엄이 있어 중기 불확실성 반영이 상대적으로 큽니다.")
            else:
                lines.append("ATM IV 만기 구조는 비교적 평탄해 단기/중기 위험 프리미엄 차이가 크지 않습니다.")

    if not np.isnan(recent_atr):
        lines.append(f"최근 ATR14는 약 {_fmt_price(recent_atr)} 수준으로 일중 변동 폭 관리가 필요합니다.")

    if not lines:
        lines.append("옵션 데이터가 제한적이라 신호 강도 해석은 보수적으로 접근해야 합니다.")
    return lines[:4]


def _build_trend_summary(curr: pd.Series, p1d: pd.Series, p1m: pd.Series, df_all: pd.DataFrame) -> dict[str, object]:
    ma200 = _safe_num(curr.get("MA200"))
    ma20 = _safe_num(curr.get("MA20"))
    ma50 = _safe_num(curr.get("MA50"))
    p1d_ma20 = _safe_num(p1d.get("MA20"))
    p1d_ma50 = _safe_num(p1d.get("MA50"))
    p1m_ma200 = _safe_num(p1m.get("MA200"))

    long_trend = "BULL" if not np.isnan(ma200) and _safe_num(curr.get("Close")) > ma200 else "BEAR"
    short_trend = "BULL" if not np.isnan(ma20) and not np.isnan(ma50) and ma20 > ma50 else "BEAR"
    divergence = _check_divergence(df_all)
    ma200_slope = (
        (_safe_num(curr.get("MA200")) / (p1m_ma200 + 1e-9) - 1) * 100
        if not np.isnan(ma200) and not np.isnan(p1m_ma200)
        else float("nan")
    )

    cross = None
    if not np.isnan(p1d_ma20) and not np.isnan(p1d_ma50) and not np.isnan(ma20) and not np.isnan(ma50):
        if p1d_ma20 < p1d_ma50 and ma20 >= ma50:
            cross = "GOLDEN CROSS"
        elif p1d_ma20 > p1d_ma50 and ma20 <= ma50:
            cross = "DEATH CROSS"

    return {
        "long_trend": long_trend,
        "short_trend": short_trend,
        "divergence": divergence,
        "ma200_slope": ma200_slope,
        "cross": cross,
    }


def _render_html(
    as_of: dt.datetime,
    out_path: Path,
    price_df: pd.DataFrame,
    opt_df: pd.DataFrame,
    expiries: list[str],
    spot: float,
) -> str:
    curr = price_df.iloc[-1]
    p1d = _get_past_row(price_df, 1)
    p1w = _get_past_row(price_df, 5)
    p1m = _get_past_row(price_df, 21)

    pcr_oi = (
        opt_df.loc[opt_df["type"] == "put", "openInterest"].sum()
        / (opt_df.loc[opt_df["type"] == "call", "openInterest"].sum() + 1e-9)
    )
    pcr_vol = (
        opt_df.loc[opt_df["type"] == "put", "volume"].sum()
        / (opt_df.loc[opt_df["type"] == "call", "volume"].sum() + 1e-9)
    )
    max_pain = _compute_max_pain(opt_df)
    term_df = _compute_term_structure(opt_df, spot)
    smc_result = _analyze_smc_amd_flow(price_df)
    macro_stats = _analyze_macro(price_df)
    trend_info = _build_trend_summary(curr, p1d, p1m, price_df)
    composite_score = _compute_composite_score(curr, macro_stats, smc_result)
    poc_price = _calculate_volume_profile_poc(price_df.tail(60))

    oi_total = (
        opt_df.groupby("strike", as_index=False)["openInterest"]
        .sum()
        .sort_values("openInterest", ascending=False)
        .head(5)
    )

    fig_price = _build_price_figure(price_df)
    fig_volume = _build_volume_figure(price_df)
    fig_macd = _build_macd_figure(price_df)
    fig_oi = _build_oi_figure(opt_df, expiries[0])
    fig_term = _build_term_structure_figure(
        term_df if not term_df.empty else pd.DataFrame({"dte": [], "atm_iv": [], "expiry": []})
    )
    fig_surface = _build_surface_figure(opt_df)

    price_div = to_html(fig_price, include_plotlyjs="cdn", full_html=False)
    volume_div = to_html(fig_volume, include_plotlyjs=False, full_html=False)
    macd_div = to_html(fig_macd, include_plotlyjs=False, full_html=False)
    oi_div = to_html(fig_oi, include_plotlyjs=False, full_html=False)
    term_div = to_html(fig_term, include_plotlyjs=False, full_html=False)
    surface_div = to_html(fig_surface, include_plotlyjs=False, full_html=False)

    conclusion_lines = _build_conclusion(
        spot=spot,
        max_pain=max_pain,
        pcr_oi=float(pcr_oi),
        pcr_vol=float(pcr_vol),
        term_df=term_df,
        recent_atr=_safe_num(curr.get("ATR14")),
    )

    top_oi_rows = "".join(
        [
            f"<tr><td>{row.strike:.2f}</td><td>{int(row.openInterest):,}</td></tr>"
            for row in oi_total.itertuples(index=False)
        ]
    )
    if not top_oi_rows:
        top_oi_rows = "<tr><td colspan='2'>데이터 없음</td></tr>"

    term_rows = ""
    for row in term_df.itertuples(index=False):
        term_rows += (
            f"<tr><td>{html.escape(str(row.expiry))}</td>"
            f"<td>{int(row.dte)}</td><td>{row.atm_iv:.2f}%</td></tr>"
        )
    if not term_rows:
        term_rows = "<tr><td colspan='3'>데이터 없음</td></tr>"

    def _v(row: pd.Series, key: str) -> float:
        return _safe_num(row.get(key))

    def _avwap_gap(row: pd.Series) -> float:
        close = _safe_num(row.get("Close"))
        avwap = _safe_num(row.get("AVWAP"))
        if np.isnan(close) or np.isnan(avwap):
            return float("nan")
        return (close / (avwap + 1e-9) - 1) * 100

    def _fmt_metric(value: float) -> str:
        return "N/A" if np.isnan(value) else f"{value:,.2f}"

    indicator_metrics = [
        ("RSI (강도)", _v(curr, "RSI"), _v(p1d, "RSI"), _v(p1w, "RSI"), _v(p1m, "RSI")),
        ("AVWAP 괴리율 (%)", _avwap_gap(curr), _avwap_gap(p1d), _avwap_gap(p1w), _avwap_gap(p1m)),
        ("BB 폭 (변동성)", _v(curr, "BB_Width"), _v(p1d, "BB_Width"), _v(p1w, "BB_Width"), _v(p1m, "BB_Width")),
        ("20일 수익률 (%)", _v(curr, "Rolling_Ret"), _v(p1d, "Rolling_Ret"), _v(p1w, "Rolling_Ret"), _v(p1m, "Rolling_Ret")),
        ("ATR (변동범위)", _v(curr, "ATR14"), _v(p1d, "ATR14"), _v(p1w, "ATR14"), _v(p1m, "ATR14")),
    ]

    indicator_rows = ""
    for name, c_v, v1d, v1w, v1m in indicator_metrics:
        d1 = float("nan") if np.isnan(c_v) or np.isnan(v1d) else c_v - v1d
        d7 = float("nan") if np.isnan(c_v) or np.isnan(v1w) else c_v - v1w
        d21 = float("nan") if np.isnan(c_v) or np.isnan(v1m) else c_v - v1m
        indicator_rows += (
            f"<tr><td>{html.escape(name)}</td><td>{_fmt_metric(c_v)}</td>"
            f"<td>{_fmt_delta(d1)}</td><td>{_fmt_delta(d7)}</td><td>{_fmt_delta(d21)}</td></tr>"
        )

    status_text = (
        "적극 매수/보유"
        if composite_score > 70
        else "관망/분할 매수"
        if composite_score > 50
        else "리스크 관리/현금 확보"
    )
    score_tone = "#16a34a" if composite_score > 70 else "#ca8a04" if composite_score > 50 else "#dc2626"
    ma200_slope = _safe_num(trend_info.get("ma200_slope"))
    avwap_now = _safe_num(curr.get("AVWAP"))

    report_lines: list[str] = [
        f"종합 점수: {composite_score:.1f}/100 | 현재 권장 포지션: [{status_text}]",
        f"추세 분석: 장기({trend_info['long_trend']}) / 단기({trend_info['short_trend']}) | MA200 기울기(1M): {_fmt_pct(ma200_slope)}",
        f"수급 분석: Order Flow={smc_result['order_flow']} | AMD 국면={smc_result['amd_phase']}",
        f"모멘텀 점검: RSI 다이버전스 = {trend_info['divergence']}",
    ]
    if trend_info.get("cross"):
        report_lines.append(f"이평선 크로스 감지: {trend_info['cross']}")
    if smc_result.get("sweep_low"):
        report_lines.append("유동성 Sweep Low 신호가 감지되어 단기 반등 시도를 체크할 구간입니다.")
    if smc_result.get("sweep_high"):
        report_lines.append("유동성 Sweep High 신호가 감지되어 고점 돌파 실패 리스크를 주의해야 합니다.")
    if not np.isnan(poc_price):
        report_lines.append(f"가격 방어선: POC(최대 매물대) = {_fmt_price(poc_price)}")
    if not np.isnan(avwap_now):
        report_lines.append(f"기관 평균 단가 추정(AVWAP): {_fmt_price(avwap_now)}")
    if not np.isnan(max_pain):
        report_lines.append(f"옵션 집중 가격(Max Pain): {_fmt_price(max_pain)}")
    report_html = "".join([f"<li>{html.escape(line)}</li>" for line in report_lines])

    if macro_stats:
        macro_lines = [
            f"달러 인덱스(DXY): {_safe_num(macro_stats['dollar_idx']):.2f} | QQQ 상관(60D): {_safe_num(macro_stats['dxy_corr']):.2f}",
            f"미 10년물(^TNX): {_safe_num(macro_stats['yield_10y']):.2f}% | QQQ 상관(60D): {_safe_num(macro_stats['yield_corr']):.2f}",
            f"반도체(SOXX) 동조화(60D): {_safe_num(macro_stats['soxx_corr']) * 100:.1f}%",
            f"VIX 레짐: {_safe_num(macro_stats['vix_curr']):.2f} ({macro_stats['vix_status']})",
            f"QQQ/SPY 상대강도 변화(20D): {_safe_num(macro_stats['rs_slope_20d']):.2f}%",
        ]
    else:
        macro_lines = ["거시 보조 지표를 충분히 수집하지 못해 기술/옵션 신호 중심으로 해석했습니다."]
    macro_html = "".join([f"<li>{html.escape(line)}</li>" for line in macro_lines])

    glossary_rows = "".join(
        [
            "<tr><td>SMC</td><td>시장 구조와 유동성(고점/저점 사냥)을 기반으로 흐름을 해석하는 방법입니다.</td></tr>",
            "<tr><td>AVWAP</td><td>특정 기준 시점 이후의 거래량 가중 평균가격으로, 기관 평균 단가 추정에 씁니다.</td></tr>",
            "<tr><td>POC</td><td>거래가 가장 많이 몰린 가격대로 지지/저항 후보가 됩니다.</td></tr>",
            "<tr><td>Max Pain</td><td>옵션 매수자 손실이 커지는 이론 가격으로 만기 전 핀 압력에 참고합니다.</td></tr>",
            "<tr><td>VIX</td><td>미국 증시의 단기 공포 수준을 나타내는 변동성 지수입니다.</td></tr>",
        ]
    )

    conclusion_html = "".join([f"<li>{html.escape(line)}</li>" for line in conclusion_lines])

    html_doc = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>나스닥 옵션 분석 (QQQ)</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --card: #ffffff;
      --ink: #0f172a;
      --muted: #475569;
      --line: #dbe2ea;
      --accent: #1d4ed8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #eef3ff 0%, var(--bg) 35%, var(--bg) 100%);
      color: var(--ink);
      font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
      line-height: 1.55;
    }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 28px 16px 48px; }}
    .hero {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 18px 20px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
      margin-bottom: 16px;
    }}
    h1 {{ margin: 0 0 6px; font-size: 28px; }}
    h2 {{ margin: 0 0 12px; font-size: 20px; }}
    p.meta {{ margin: 4px 0; color: var(--muted); }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }}
    .metric {{
      background: #f8fafc;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
    }}
    .metric .label {{ font-size: 13px; color: var(--muted); }}
    .metric .value {{ font-size: 18px; font-weight: 700; margin-top: 4px; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px 14px 8px;
      margin-top: 14px;
      box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      background: #fff;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 10px;
      text-align: right;
    }}
    th:first-child, td:first-child {{ text-align: left; }}
    ul {{ margin: 6px 0 14px; padding-left: 20px; }}
    .foot {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 14px;
    }}
    .score {{
      display: inline-block;
      font-weight: 800;
      padding: 4px 10px;
      border-radius: 999px;
      background: #f1f5f9;
      margin-left: 6px;
    }}
    .muted {{
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>나스닥 옵션 분석 (QQQ)</h1>
      <p class="meta">as of (KST): {as_of.strftime("%Y-%m-%d %H:%M:%S")}</p>
      <p class="meta">데이터 상태: yfinance 기준 최근 체결/전일 종가 혼합 (지연 가능)</p>
      <p class="meta">파일: {html.escape(str(out_path))}</p>
      <div class="grid">
        <div class="metric"><div class="label">QQQ 현재가</div><div class="value">{_fmt_price(_safe_num(curr.get("Close")))}</div></div>
        <div class="metric"><div class="label">1D 변화율</div><div class="value">{_fmt_pct(_safe_num(curr.get("RET_1D")))}</div></div>
        <div class="metric"><div class="label">5D 변화율</div><div class="value">{_fmt_pct(_safe_num(curr.get("RET_5D")))}</div></div>
        <div class="metric"><div class="label">1M 변화율</div><div class="value">{_fmt_pct(_safe_num(curr.get("RET_1M")))}</div></div>
        <div class="metric"><div class="label">Put/Call (OI)</div><div class="value">{_fmt_ratio(float(pcr_oi))}</div></div>
        <div class="metric"><div class="label">Put/Call (Volume)</div><div class="value">{_fmt_ratio(float(pcr_vol))}</div></div>
        <div class="metric"><div class="label">Max Pain</div><div class="value">{_fmt_price(max_pain)}</div></div>
        <div class="metric"><div class="label">POC</div><div class="value">{_fmt_price(poc_price)}</div></div>
        <div class="metric"><div class="label">AVWAP</div><div class="value">{_fmt_price(avwap_now)}</div></div>
        <div class="metric"><div class="label">수집 만기 수</div><div class="value">{len(expiries)}</div></div>
      </div>
    </section>

    <section class="card">
      <h2>1. 시장 스냅샷</h2>
      {price_div}
      {volume_div}
      {macd_div}
    </section>

    <section class="card">
      <h2>2. 옵션체인 핵심</h2>
      <h3>2.1 최근 만기 OI 분포</h3>
      {oi_div}
      <h3>2.2 ATM IV 만기 구조</h3>
      {term_div}
      <h3>2.3 3D IV Surface</h3>
      {surface_div}
    </section>

    <section class="card">
      <h2>3. QQQ 실시간 지표 요약</h2>
      <table>
        <thead>
          <tr><th>Metric</th><th>Current</th><th>vs 1D</th><th>vs 1W</th><th>vs 1M</th></tr>
        </thead>
        <tbody>{indicator_rows}</tbody>
      </table>
    </section>

    <section class="card">
      <h2>4. 상세 종합 분석 보고서 <span class="score" style="color:{score_tone}">{composite_score:.1f}/100</span></h2>
      <p class="muted">현재 권장 포지션: {html.escape(status_text)}</p>
      <h3>4.1 핵심 해석</h3>
      <ul>{report_html}</ul>
      <h3>4.2 외부 지표 및 거시 환경</h3>
      <ul>{macro_html}</ul>
      <h3>4.3 옵션/포지셔닝 체크</h3>
      <h3>4.3.1 OI 집중 스트라이크 (Top 5)</h3>
      <table>
        <thead><tr><th>Strike</th><th>Total OI</th></tr></thead>
        <tbody>{top_oi_rows}</tbody>
      </table>
      <h3>4.3.2 ATM IV 테이블</h3>
      <table>
        <thead><tr><th>Expiry</th><th>DTE</th><th>ATM IV</th></tr></thead>
        <tbody>{term_rows}</tbody>
      </table>
    </section>

    <section class="card">
      <h2>5. 초보자를 위한 용어 가이드</h2>
      <table>
        <thead><tr><th>용어</th><th>설명</th></tr></thead>
        <tbody>{glossary_rows}</tbody>
      </table>
    </section>

    <section class="card">
      <h2>결론</h2>
      <ul>{conclusion_html}</ul>
      <p class="foot">본 자료는 정보 제공 목적이며 투자 자문이 아닙니다. 데이터 지연/누락 가능성이 있습니다.</p>
    </section>
  </div>
</body>
</html>
"""
    return html_doc


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="QQQ 나스닥 옵션 분석 HTML 리포트 생성기")
    p.add_argument("--period", default="2y", help="가격 히스토리 기간 (기본: 2y)")
    p.add_argument("--max-exp", type=int, default=5, help="수집할 옵션 만기 개수 (기본: 5)")
    p.add_argument(
        "--strike-band",
        type=float,
        default=0.12,
        help="현물 대비 스트라이크 필터 비율 (기본: 0.12 = ±12%%)",
    )
    p.add_argument("--outdir", default="reports", help="출력 디렉터리 (기본: reports)")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    as_of = _now_kst()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"nasdaq_option_analysis_qqq_{as_of.strftime('%Y%m%d_%H%M%S')}_kst"
    out_path = outdir / f"{stem}.html"

    price_df = _prepare_price_data(args.period)
    opt_df, expiries, spot = _fetch_option_data(args.max_exp, args.strike_band)

    html_doc = _render_html(
        as_of=as_of,
        out_path=out_path,
        price_df=price_df,
        opt_df=opt_df,
        expiries=expiries,
        spot=spot,
    )
    out_path.write_text(html_doc, encoding="utf-8")

    print(f"saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
