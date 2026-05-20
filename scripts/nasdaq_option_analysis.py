#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import math
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

try:
    import plotly.graph_objects as go
    from plotly.io import to_html as plotly_to_html
except ModuleNotFoundError:
    go = None
    plotly_to_html = None


KST = ZoneInfo("Asia/Seoul")
HAS_PLOTLY = go is not None and plotly_to_html is not None
UNDERLYING_SYMBOL = "^NDX"
UNDERLYING_LABEL = "NDX"
REPORT_SLUG = "ndx"
VFTW1_SYMBOL = "^VFTW1"
VFTW2_SYMBOL = "^VFTW2"
VX_PROXY_FRONT_SYMBOL = "VIXY"
VX_PROXY_SECOND_SYMBOL = "VIXM"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _venv_python() -> Path:
    return _project_root() / ".venv" / "bin" / "python"


def _now_kst() -> dt.datetime:
    return dt.datetime.now(tz=KST)


def _ensure_supported_runtime() -> None:
    current_python = Path(sys.executable)
    venv_python = _venv_python()
    venv_root = venv_python.parent.parent
    current_prefix = Path(sys.prefix)

    if venv_python.exists() and current_prefix != venv_root:
        raise SystemExit(
            "이 스크립트는 프로젝트 가상환경으로 실행해야 합니다.\n"
            f"현재 인터프리터: {current_python}\n"
            f"현재 prefix: {current_prefix}\n"
            f"권장 인터프리터: {venv_python}\n"
            f"실행 예시: {venv_python} {Path(__file__).resolve()} --period 2y --max-exp 20 --outdir reports"
        )

    if not HAS_PLOTLY:
        install_hint = (
            f"uv pip install --python {venv_python} plotly"
            if venv_python.exists()
            else "python3 -m pip install plotly"
        )
        raise SystemExit(
            "plotly 패키지가 현재 실행 환경에 없습니다.\n"
            f"현재 인터프리터: {current_python}\n"
            f"설치 예시: {install_hint}"
        )


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
    return f"{value:,.2f}"


def _fmt_pct(value: float) -> str:
    if np.isnan(value):
        return "N/A"
    return f"{value:.2f}%"


def _fmt_ratio(value: float) -> str:
    if np.isnan(value):
        return "N/A"
    return f"{value:.2f}"


def _fmt_sigma(value: float) -> str:
    if np.isnan(value):
        return "N/A"
    return f"{value:.2f}σ"


def _fmt_delta(value: float) -> str:
    if np.isnan(value):
        return "N/A"
    return f"{value:+.2f}"


def _zscore_state(zscore: float) -> str:
    if np.isnan(zscore):
        return "판정 유보"
    if zscore >= 3:
        return "상방 초과열"
    if zscore >= 2:
        return "상방 과열"
    if zscore >= 1:
        return "상방 확장"
    if zscore <= -3:
        return "하방 초과매도"
    if zscore <= -2:
        return "하방 과매도"
    if zscore <= -1:
        return "하방 확장"
    return "중립권"


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _black_scholes_price(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    sigma: float,
    option_type: str,
    dividend_yield: float = 0.0,
) -> float:
    intrinsic = max(spot - strike, 0.0) if option_type == "call" else max(strike - spot, 0.0)
    if time_years <= 0 or sigma <= 0:
        return intrinsic

    vol_term = sigma * math.sqrt(time_years)
    if vol_term <= 0:
        return intrinsic

    d1 = (
        math.log(max(spot, 1e-9) / max(strike, 1e-9))
        + (rate - dividend_yield + 0.5 * sigma * sigma) * time_years
    ) / vol_term
    d2 = d1 - vol_term
    disc_r = math.exp(-rate * time_years)
    disc_q = math.exp(-dividend_yield * time_years)

    if option_type == "call":
        return spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
    return strike * disc_r * _norm_cdf(-d2) - spot * disc_q * _norm_cdf(-d1)


def _estimate_implied_volatility(
    option_price: float,
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    option_type: str,
) -> float:
    if any(np.isnan(v) for v in [option_price, spot, strike, time_years, rate]):
        return float("nan")
    intrinsic = max(spot - strike, 0.0) if option_type == "call" else max(strike - spot, 0.0)
    if option_price <= intrinsic + 1e-6 or time_years <= 0:
        return float("nan")

    low, high = 1e-4, 5.0
    try:
        for _ in range(80):
            mid = (low + high) / 2
            model_price = _black_scholes_price(spot, strike, time_years, rate, mid, option_type)
            if model_price > option_price:
                high = mid
            else:
                low = mid
        return float((low + high) / 2)
    except (OverflowError, ValueError, ZeroDivisionError):
        return float("nan")


def _resolve_option_price(row: pd.Series) -> float:
    bid = _safe_num(row.get("bid"))
    ask = _safe_num(row.get("ask"))
    last_price = _safe_num(row.get("lastPrice"))

    if not np.isnan(bid) and not np.isnan(ask) and bid > 0 and ask > 0:
        return float((bid + ask) / 2)
    if not np.isnan(last_price) and last_price > 0:
        return float(last_price)
    if not np.isnan(bid) and bid > 0:
        return float(bid)
    if not np.isnan(ask) and ask > 0:
        return float(ask)
    return float("nan")


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


def _check_zscore_divergence(df: pd.DataFrame, window: int = 20) -> str:
    if len(df) < window + 1:
        return "None"
    cp, pp = _safe_num(df["Close"].iloc[-1]), _safe_num(df["Close"].iloc[-window])
    cr, pr = _safe_num(df["ZSCORE120"].iloc[-1]), _safe_num(df["ZSCORE120"].iloc[-window])
    if any(np.isnan(v) for v in [cp, pp, cr, pr]):
        return "None"
    if cp > pp and cr < pr:
        return "BEARISH (P↑ Z↓)"
    if cp < pp and cr > pr:
        return "BULLISH (P↓ Z↑)"
    return "None"


def _calculate_supertrend(
    df: pd.DataFrame, atr_window: int = 10, multiplier: float = 3.0
) -> tuple[pd.Series, pd.Series]:
    if df.empty or "ATR10" not in df.columns:
        return pd.Series(np.nan, index=df.index), pd.Series("UNKNOWN", index=df.index, dtype="object")

    hl2 = (df["High"] + df["Low"]) / 2.0
    basic_upper = hl2 + multiplier * df["ATR10"]
    basic_lower = hl2 - multiplier * df["ATR10"]

    final_upper = pd.Series(np.nan, index=df.index, dtype="float64")
    final_lower = pd.Series(np.nan, index=df.index, dtype="float64")
    direction = pd.Series("UNKNOWN", index=df.index, dtype="object")
    supertrend = pd.Series(np.nan, index=df.index, dtype="float64")

    prev_dir = "BULL"
    for i, idx in enumerate(df.index):
        bu = _safe_num(basic_upper.iloc[i])
        bl = _safe_num(basic_lower.iloc[i])
        close = _safe_num(df["Close"].iloc[i])
        if np.isnan(bu) or np.isnan(bl) or np.isnan(close):
            continue

        if i == 0 or np.isnan(final_upper.iloc[i - 1]) or np.isnan(final_lower.iloc[i - 1]):
            final_upper.iloc[i] = bu
            final_lower.iloc[i] = bl
            prev_dir = "BULL" if close >= hl2.iloc[i] else "BEAR"
        else:
            prev_close = _safe_num(df["Close"].iloc[i - 1])
            prev_upper = _safe_num(final_upper.iloc[i - 1])
            prev_lower = _safe_num(final_lower.iloc[i - 1])

            final_upper.iloc[i] = bu if bu < prev_upper or prev_close > prev_upper else prev_upper
            final_lower.iloc[i] = bl if bl > prev_lower or prev_close < prev_lower else prev_lower

            if close > prev_upper:
                prev_dir = "BULL"
            elif close < prev_lower:
                prev_dir = "BEAR"

        direction.iloc[i] = prev_dir
        supertrend.iloc[i] = final_lower.iloc[i] if prev_dir == "BULL" else final_upper.iloc[i]

    return supertrend, direction


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


def _analyze_macro(df_underlying: pd.DataFrame, lookback: int = 60) -> dict[str, float | str] | None:
    try:
        macro_tickers = ["^TNX", "SPY", "^VIX", "DX-Y.NYB", "SOXX"]
        raw = yf.download(macro_tickers, period="2y", progress=False, auto_adjust=True)
        if raw.empty:
            return None
        macro_data = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
        if isinstance(macro_data.columns, pd.MultiIndex):
            macro_data.columns = macro_data.columns.get_level_values(0)

        def _normalized_dates(index: pd.Index) -> pd.DatetimeIndex:
            dates = pd.DatetimeIndex(pd.to_datetime(index))
            if dates.tz is not None:
                dates = dates.tz_localize(None)
            return dates.normalize()

        underlying_close = df_underlying["Close"].copy()
        underlying_close.index = _normalized_dates(underlying_close.index)
        macro_data = macro_data.copy()
        macro_data.index = _normalized_dates(macro_data.index)

        combined = pd.concat([underlying_close.rename(UNDERLYING_LABEL), macro_data], axis=1, join="inner")
        combined = combined.ffill().dropna()
        combined.columns = [UNDERLYING_LABEL] + list(macro_data.columns)
        if len(combined) < max(lookback + 5, 40):
            return None

        pct = combined.pct_change()
        yield_corr = _safe_num(pct[UNDERLYING_LABEL].rolling(lookback).corr(pct["^TNX"]).iloc[-1])
        dxy_corr = _safe_num(pct[UNDERLYING_LABEL].rolling(lookback).corr(pct["DX-Y.NYB"]).iloc[-1])
        soxx_corr = _safe_num(pct[UNDERLYING_LABEL].rolling(lookback).corr(pct["SOXX"]).iloc[-1])
        rs_slope = _safe_num((combined[UNDERLYING_LABEL] / combined["SPY"]).pct_change(20).iloc[-1] * 100)
        vix_curr = _safe_num(combined["^VIX"].iloc[-1])
        vix_status = "UNKNOWN" if np.isnan(vix_curr) else ("CALM" if vix_curr < 20 else "FEAR")

        return {
            "yield_corr": yield_corr,
            "yield_10y": _safe_num(combined["^TNX"].iloc[-1]),
            "dxy_corr": dxy_corr,
            "dollar_idx": _safe_num(combined["DX-Y.NYB"].iloc[-1]),
            "soxx_corr": soxx_corr,
            "vix_curr": vix_curr,
            "vix_status": vix_status,
            "rs_slope_20d": rs_slope,
        }
    except Exception:
        return None


def _compute_composite_score(
    curr: pd.Series, macro: dict[str, float | str] | None, smc: dict[str, object]
) -> float:
    zscore = _safe_num(curr.get("ZSCORE120"))
    ma120_gap = _safe_num(curr.get("MA120_GAP"))

    z_balance = max(0, 3.5 - abs(zscore)) * 8 if not np.isnan(zscore) else 10
    trend_score = np.tanh((0 if np.isnan(ma120_gap) else ma120_gap) / 6) * 20
    overheat_penalty = -8 if not np.isnan(zscore) and abs(zscore) >= 3 else 0
    tech_score = z_balance + trend_score + overheat_penalty

    if macro is None:
        base = tech_score + 30
    else:
        vix_status = macro.get("vix_status")
        macro_bonus = 10 if vix_status == "CALM" else -10 if vix_status == "FEAR" else 0
        dxy_corr = _safe_num(macro.get("dxy_corr"))
        dxy_bonus = 0 if np.isnan(dxy_corr) else 5 if dxy_corr < 0 else -5
        base = tech_score + macro_bonus + dxy_bonus + 30

    smc_bonus = 5 if smc.get("sweep_low") else (-5 if smc.get("sweep_high") else 0)
    return float(np.clip(base + smc_bonus, 0, 100))


def _prepare_price_data(period: str) -> pd.DataFrame:
    df = yf.download(UNDERLYING_SYMBOL, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        raise RuntimeError(f"{UNDERLYING_LABEL} 가격 데이터를 가져오지 못했습니다.")

    out = df.copy()
    out["MA120"] = out["Close"].rolling(120, min_periods=60).mean()
    out["MA120_RESID"] = out["Close"] - out["MA120"]
    out["MA120_SIGMA"] = out["MA120_RESID"].rolling(120, min_periods=60).std()
    out["ZSCORE120"] = out["MA120_RESID"] / (out["MA120_SIGMA"] + 1e-9)
    out["MA120_GAP"] = out["MA120_RESID"] / (out["MA120"] + 1e-9) * 100
    for sigma in (1, 2, 3):
        out[f"MA120_P{sigma}"] = out["MA120"] + out["MA120_SIGMA"] * sigma
        out[f"MA120_M{sigma}"] = out["MA120"] - out["MA120_SIGMA"] * sigma
    out["Avg_Vol"] = out["Volume"].rolling(20, min_periods=5).mean()
    out["Traded_Value"] = out["Close"] * out["Volume"]
    out["Avg_Traded_Value"] = out["Traded_Value"].rolling(20, min_periods=5).mean()
    out["RET_1D"] = out["Close"].pct_change(1) * 100
    out["RET_5D"] = out["Close"].pct_change(5) * 100
    out["RET_1M"] = out["Close"].pct_change(21) * 100
    out["Daily_Return"] = out["Close"].pct_change()
    out["Volatility"] = out["Daily_Return"].rolling(20, min_periods=10).std(ddof=0) * np.sqrt(365) * 100

    tr = pd.concat(
        [
            out["High"] - out["Low"],
            (out["High"] - out["Close"].shift()).abs(),
            (out["Low"] - out["Close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["ATR10"] = tr.rolling(10).mean()
    out["ATR14"] = tr.rolling(14).mean()
    out["SUPERTREND_10_3"], out["SUPERTREND_10_3_DIR"] = _calculate_supertrend(out, 10, 3.0)
    out["RV20"] = out["Volatility"]
    out["Rolling_Ret"] = out["Close"].pct_change(20) * 100

    anchor_lookback = out["Low"].tail(min(120, len(out)))
    anchor_idx = anchor_lookback.idxmin() if not anchor_lookback.empty else out.index[0]
    out["AVWAP"] = _calculate_anchored_vwap(out, anchor_idx)
    return out


def _extract_close_frame(raw: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" not in raw.columns.get_level_values(0):
            return pd.DataFrame()
        close = raw["Close"].copy()
    else:
        if "Close" not in raw.columns:
            return pd.DataFrame()
        close = raw[["Close"]].rename(columns={"Close": symbols[0] if symbols else "UNKNOWN"})

    if isinstance(close, pd.Series):
        close = close.to_frame(name=symbols[0] if symbols else "UNKNOWN")
    close = close.copy()
    close.columns = [str(c) for c in close.columns]
    idx = pd.DatetimeIndex(pd.to_datetime(close.index))
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    close.index = idx.normalize()
    return close


def _prepare_vftw_snapshot_data() -> pd.DataFrame:
    try:
        raw = yf.download(
            [VFTW1_SYMBOL, VFTW2_SYMBOL],
            period="5d",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        return pd.DataFrame()

    close = _extract_close_frame(raw, [VFTW1_SYMBOL, VFTW2_SYMBOL])
    if close.empty or VFTW1_SYMBOL not in close.columns or VFTW2_SYMBOL not in close.columns:
        return pd.DataFrame()

    out = close[[VFTW1_SYMBOL, VFTW2_SYMBOL]].rename(columns={VFTW1_SYMBOL: "VX1", VFTW2_SYMBOL: "VX2"})
    out = out.apply(pd.to_numeric, errors="coerce").dropna(subset=["VX1", "VX2"])
    out = out[out["VX2"] != 0]
    if out.empty:
        return out

    out["VX1_DIV_VX2"] = out["VX1"] / out["VX2"]
    out["VFTW_HAPPINESS"] = (out["VX1_DIV_VX2"] - 1.0) * -100.0
    return out


def _prepare_vx_proxy_momentum_data(period: str) -> pd.DataFrame:
    try:
        raw = yf.download(
            [VX_PROXY_FRONT_SYMBOL, VX_PROXY_SECOND_SYMBOL],
            period=period,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        return pd.DataFrame()

    close = _extract_close_frame(raw, [VX_PROXY_FRONT_SYMBOL, VX_PROXY_SECOND_SYMBOL])
    if close.empty or VX_PROXY_FRONT_SYMBOL not in close.columns or VX_PROXY_SECOND_SYMBOL not in close.columns:
        return pd.DataFrame()

    out = close[[VX_PROXY_FRONT_SYMBOL, VX_PROXY_SECOND_SYMBOL]].rename(
        columns={VX_PROXY_FRONT_SYMBOL: "VIXY", VX_PROXY_SECOND_SYMBOL: "VIXM"}
    )
    out = out.apply(pd.to_numeric, errors="coerce").dropna(subset=["VIXY", "VIXM"])
    out = out[out["VIXM"] != 0]
    if out.empty:
        return out

    out["VIXY_DIV_VIXM"] = out["VIXY"] / out["VIXM"]
    out["VX_PROXY_MOMENTUM"] = (out["VIXY_DIV_VIXM"] - 1.0) * -100.0
    return out


def _fetch_option_data(max_exp: int, strike_band: float) -> tuple[pd.DataFrame, list[str], float]:
    ticker = yf.Ticker(UNDERLYING_SYMBOL)
    expiries = list(ticker.options[:max_exp])
    if not expiries:
        raise RuntimeError(f"{UNDERLYING_LABEL} 옵션 만기 정보를 가져오지 못했습니다.")

    hist = ticker.history(period="5d", auto_adjust=False)
    if hist.empty:
        raise RuntimeError(f"{UNDERLYING_LABEL} 최근 종가를 가져오지 못했습니다.")
    last_close = float(hist["Close"].iloc[-1])

    frames: list[pd.DataFrame] = []
    approx_rate = 0.043
    for exp in expiries:
        oc = ticker.option_chain(exp)
        exp_date = dt.datetime.strptime(exp, "%Y-%m-%d").date()
        dte = (exp_date - _now_kst().date()).days
        time_years = max(dte, 1) / 365.0

        for opt_type, src in (("call", oc.calls), ("put", oc.puts)):
            if src is None or src.empty:
                continue
            d = src.copy()
            d["type"] = opt_type
            d["expiry"] = exp
            d["dte"] = dte
            d["time_years"] = time_years
            frames.append(d)

    if not frames:
        raise RuntimeError("옵션체인 데이터가 비어 있습니다.")

    all_opt = pd.concat(frames, ignore_index=True)
    for col in ["strike", "openInterest", "volume", "impliedVolatility", "lastPrice", "bid", "ask"]:
        if col in all_opt.columns:
            all_opt[col] = pd.to_numeric(all_opt[col], errors="coerce")

    all_opt["impliedVolatilityRaw"] = all_opt["impliedVolatility"]
    all_opt["optionPrice"] = all_opt.apply(_resolve_option_price, axis=1)
    intrinsic = np.where(
        all_opt["type"].eq("call"),
        np.maximum(last_close - all_opt["strike"], 0.0),
        np.maximum(all_opt["strike"] - last_close, 0.0),
    )
    all_opt["calc_impliedVolatility"] = all_opt.apply(
        lambda row: _estimate_implied_volatility(
            option_price=_safe_num(row.get("optionPrice")),
            spot=last_close,
            strike=_safe_num(row.get("strike")),
            time_years=_safe_num(row.get("time_years")),
            rate=approx_rate,
            option_type=str(row.get("type")),
        ),
        axis=1,
    )
    raw_iv = all_opt["impliedVolatilityRaw"]
    calc_iv = all_opt["calc_impliedVolatility"]
    premium = all_opt["optionPrice"]
    discrepancy = calc_iv / raw_iv.replace(0, np.nan)
    replacement_mask = calc_iv.notna() & (
        raw_iv.isna()
        | (raw_iv <= 0)
        | ((premium > (intrinsic + 0.25)) & ((raw_iv < 0.08) | (discrepancy > 3.0)))
    )
    all_opt["iv_source"] = np.where(replacement_mask, "model_fallback", "yfinance")
    all_opt["impliedVolatility"] = np.where(replacement_mask, calc_iv, raw_iv)

    all_opt = all_opt.dropna(subset=["strike", "impliedVolatility"]).copy()
    all_opt = all_opt[(all_opt["impliedVolatility"] > 0.01) & (all_opt["impliedVolatility"] <= 5.0)]
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


def _compute_target_atm_iv(term_df: pd.DataFrame, target_dte: int = 30) -> float:
    if term_df.empty:
        return float("nan")
    term = term_df[["dte", "atm_iv"]].dropna().sort_values("dte")
    if term.empty:
        return float("nan")
    if len(term) == 1:
        return _safe_num(term.iloc[0]["atm_iv"])

    dtes = term["dte"].astype(float).to_numpy()
    ivs = term["atm_iv"].astype(float).to_numpy()
    if target_dte <= dtes.min() or target_dte >= dtes.max():
        nearest_idx = int(np.argmin(np.abs(dtes - target_dte)))
        return float(ivs[nearest_idx])
    return float(np.interp(float(target_dte), dtes, ivs))


def _select_expiry_near_dte(df_opt: pd.DataFrame, target_dte: int = 30) -> tuple[str | None, float]:
    if df_opt.empty:
        return None, float("nan")
    expiries = df_opt[["expiry", "dte"]].dropna().drop_duplicates().copy()
    if expiries.empty:
        return None, float("nan")
    expiries["dte_gap"] = (expiries["dte"].astype(float) - target_dte).abs()
    row = expiries.sort_values(["dte_gap", "dte", "expiry"]).iloc[0]
    return str(row["expiry"]), _safe_num(row["dte"])


def _build_price_figure(df: pd.DataFrame) -> go.Figure:
    view = df.tail(120).copy()
    fig = go.Figure()
    band_styles = [
        (3, "#fecaca", "#bfdbfe", 0.85, "dot"),
        (2, "#fca5a5", "#93c5fd", 1.0, "dash"),
        (1, "#dc2626", "#2563eb", 1.25, "solid"),
    ]
    for sigma, up_color, down_color, width, dash in band_styles:
        fig.add_trace(
            go.Scatter(
                x=view.index,
                y=view[f"MA120_P{sigma}"],
                mode="lines",
                name=f"+{sigma}σ",
                line=dict(color=up_color, width=width, dash=dash),
                opacity=0.95,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=view.index,
                y=view[f"MA120_M{sigma}"],
                mode="lines",
                name=f"-{sigma}σ",
                line=dict(color=down_color, width=width, dash=dash),
                opacity=0.95,
            )
        )
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=view["MA120"],
            mode="lines",
            name="120D Mean",
            line=dict(color="#16a34a", width=1.1),
            opacity=0.9,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=view["Close"],
            mode="lines",
            name=f"{UNDERLYING_LABEL} Close",
            line=dict(color="#0f172a", width=2.6),
        )
    )
    price_min = _safe_num(view["Close"].min())
    price_max = _safe_num(view["Close"].max())
    yaxis_range = None
    if not np.isnan(price_min) and not np.isnan(price_max) and price_max > price_min:
        pad = (price_max - price_min) * 0.08
        yaxis_range = [price_min - pad, price_max + pad]
    fig.update_layout(
        title=f"{UNDERLYING_LABEL} 가격과 120일 Z-Score 밴드 (최근 120거래일)",
        xaxis_title="Date",
        yaxis_title="Index Level",
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=40, r=20, t=60, b=40),
    )
    if yaxis_range is not None:
        fig.update_yaxes(range=yaxis_range)
    return fig


def _build_traded_value_figure(df: pd.DataFrame) -> go.Figure:
    view = df.tail(120).copy()
    traded_value_t = view["Traded_Value"] / 1e12
    avg_traded_value_t = view["Avg_Traded_Value"] / 1e12
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=view.index,
            y=traded_value_t,
            name="거래액",
            marker_color="#d1d5db",
            opacity=0.65,
            hovertemplate="%{x|%Y-%m-%d}<br>거래액=%{y:,.2f}조<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=avg_traded_value_t,
            mode="lines",
            name="20D Avg 거래액",
            line=dict(color="#2563EB", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>20D 평균=%{y:,.2f}조<extra></extra>",
        )
    )
    fig.update_layout(
        title="거래액 추이 (Close × Volume)",
        xaxis_title="Date",
        yaxis_title="거래액 (조 단위)",
        template="plotly_white",
        height=340,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _build_zscore_oscillator_figure(df: pd.DataFrame) -> go.Figure:
    view = df.tail(120).copy()
    z = view["ZSCORE120"]
    fig = go.Figure()
    z_min = _safe_num(z.min())
    z_max = _safe_num(z.max())
    y_min = min(-3.5, z_min - 0.4 if not np.isnan(z_min) else -3.5)
    y_max = max(3.5, z_max + 0.4 if not np.isnan(z_max) else 3.5)
    fig.add_hrect(y0=2, y1=3, fillcolor="#dc2626", opacity=0.08, line_width=0)
    fig.add_hrect(y0=3, y1=y_max, fillcolor="#dc2626", opacity=0.14, line_width=0)
    fig.add_hrect(y0=-3, y1=-2, fillcolor="#2563eb", opacity=0.08, line_width=0)
    fig.add_hrect(y0=y_min, y1=-3, fillcolor="#2563eb", opacity=0.14, line_width=0)
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=z,
            mode="lines",
            name="120D Z-Score",
            line=dict(color="#111827", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>Z-Score=%{y:.2f}σ<extra></extra>",
        )
    )
    for level, color, label, dash in [
        (3, "#dc2626", "+3σ 초과열", "solid"),
        (2, "#f87171", "+2σ 과열", "dash"),
        (0, "#94a3b8", "중심선", "dot"),
        (-2, "#60a5fa", "-2σ 과매도", "dash"),
        (-3, "#2563eb", "-3σ 초과매도", "solid"),
    ]:
        fig.add_trace(
            go.Scatter(
                x=[view.index.min(), view.index.max()],
                y=[level, level],
                mode="lines",
                name=label,
                line=dict(color=color, width=1, dash=dash),
                hoverinfo="skip",
            )
        )
    fig.update_layout(
        title="120일 평균 대비 Z-Score 오실레이터",
        xaxis_title="Date",
        yaxis_title="Z-Score (σ)",
        template="plotly_white",
        height=340,
        yaxis=dict(range=[y_min, y_max], zeroline=False),
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _build_vx_proxy_momentum_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df.empty or "VX_PROXY_MOMENTUM" not in df.columns:
        fig.update_layout(
            title="VX 곡선 모멘텀 프록시: ((VIXY/VIXM) - 1) × -100 (데이터 없음)",
            template="plotly_white",
            height=340,
            margin=dict(l=40, r=20, t=60, b=40),
        )
        return fig

    view = df.tail(120).copy()
    fig.add_trace(
        go.Scatter(
            x=view.index,
            y=view["VX_PROXY_MOMENTUM"],
            mode="lines",
            name="VIXY/VIXM Proxy",
            line=dict(color="#0f172a", width=2),
            customdata=np.stack([view["VIXY"], view["VIXM"], view["VIXY_DIV_VIXM"]], axis=-1),
            hovertemplate=(
                "%{x|%Y-%m-%d}<br>Proxy Momentum=%{y:.2f}"
                "<br>VIXY=%{customdata[0]:.2f}"
                "<br>VIXM=%{customdata[1]:.2f}"
                "<br>VIXY/VIXM=%{customdata[2]:.4f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title="VX 곡선 모멘텀 프록시: ((VIXY/VIXM) - 1) × -100",
        xaxis_title="Date",
        yaxis_title="Proxy Momentum",
        template="plotly_white",
        height=340,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _build_oi_figure(df_opt: pd.DataFrame, expiry: str) -> go.Figure:
    near = df_opt[df_opt["expiry"] == expiry].copy()
    call = near[near["type"] == "call"].groupby("strike", as_index=False)["openInterest"].sum()
    put = near[near["type"] == "put"].groupby("strike", as_index=False)["openInterest"].sum()

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=call["strike"],
            y=call["openInterest"],
            name=f"Call OI ({expiry})",
            marker_color="#2563EB",
            opacity=0.75,
        )
    )
    fig.add_trace(
        go.Bar(
            x=put["strike"],
            y=put["openInterest"],
            name=f"Put OI ({expiry})",
            marker_color="#DC2626",
            opacity=0.65,
        )
    )
    fig.update_layout(
        barmode="overlay",
        title=f"30D 근접 만기 OI 분포 ({expiry})",
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


def _build_skew_figure(df_opt: pd.DataFrame, spot: float, target_dte: int = 30) -> go.Figure:
    expiry, dte = _select_expiry_near_dte(df_opt, target_dte)
    fig = go.Figure()
    if expiry is None or np.isnan(dte):
        fig.update_layout(
            title="30D 변동성 스큐 (데이터 없음)",
            template="plotly_white",
            height=420,
            margin=dict(l=40, r=20, t=60, b=40),
        )
        return fig

    skew = df_opt[df_opt["expiry"] == expiry].dropna(subset=["strike", "impliedVolatility"]).copy()
    skew["moneyness_pct"] = (skew["strike"] / (spot + 1e-9) - 1.0) * 100.0
    skew["iv_pct"] = skew["impliedVolatility"] * 100.0
    skew = skew[skew["moneyness_pct"].between(-12.0, 12.0)].sort_values(["type", "moneyness_pct"])

    for opt_type, color, name in [("put", "#2563eb", "Put IV"), ("call", "#dc2626", "Call IV")]:
        part = skew[skew["type"] == opt_type].copy()
        if part.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=part["moneyness_pct"],
                y=part["iv_pct"],
                mode="lines+markers",
                name=f"{name} ({expiry})",
                line=dict(color=color, width=2),
                marker=dict(size=5, opacity=0.75),
                customdata=np.stack([part["strike"], part["openInterest"].fillna(0), part["volume"].fillna(0)], axis=-1),
                hovertemplate=(
                    "Moneyness=%{x:.2f}%<br>IV=%{y:.2f}%"
                    "<br>Strike=%{customdata[0]:,.0f}"
                    "<br>OI=%{customdata[1]:,.0f}"
                    "<br>Volume=%{customdata[2]:,.0f}<extra></extra>"
                ),
            )
        )

    fig.add_vline(x=0, line_color="#64748b", line_width=1, line_dash="dot")
    fig.update_layout(
        title=f"{UNDERLYING_LABEL} 30D 변동성 스큐 ({expiry}, DTE {int(dte)})",
        xaxis_title="Moneyness vs Spot (%)",
        yaxis_title="Implied Volatility (%)",
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=40, r=20, t=60, b=40),
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


def _level_gap_pct(price: float, level: float) -> float:
    if np.isnan(price) or np.isnan(level) or level == 0:
        return float("nan")
    return (price / level - 1.0) * 100.0


def _build_data_interpretation_paragraphs(
    curr: pd.Series,
    pcr_oi: float,
    pcr_vol: float,
    max_pain: float,
    term_df: pd.DataFrame,
    oi_total: pd.DataFrame,
    macro_stats: dict[str, float | str] | None,
    trend_info: dict[str, object],
    smc_result: dict[str, object],
    poc_price: float,
    avwap_now: float,
) -> list[str]:
    close = _safe_num(curr.get("Close"))
    ret_1d = _safe_num(curr.get("RET_1D"))
    ret_5d = _safe_num(curr.get("RET_5D"))
    ret_1m = _safe_num(curr.get("RET_1M"))
    volatility = _safe_num(curr.get("Volatility"))
    atr14 = _safe_num(curr.get("ATR14"))
    ma120 = _safe_num(curr.get("MA120"))
    zscore = _safe_num(curr.get("ZSCORE120"))
    ma120_gap = _safe_num(curr.get("MA120_GAP"))

    avwap_gap = _level_gap_pct(close, avwap_now)
    poc_gap = _level_gap_pct(close, poc_price)
    max_pain_gap = _level_gap_pct(close, max_pain)
    z_state = _zscore_state(zscore)

    if np.isnan(zscore):
        zscore_tone = "Z-Score 기반 모멘텀 판정은 중립으로 유보하는 편이 좋습니다."
    elif abs(zscore) >= 3:
        zscore_tone = "Z-Score가 3σ 밖에 있어 추격보다 되돌림 리스크 관리가 중요한 구간입니다."
    elif abs(zscore) >= 2:
        zscore_tone = "Z-Score가 2σ 밖에 있어 단기 과열/과매도 구간 진입을 의식해야 합니다."
    else:
        zscore_tone = "Z-Score가 2σ 안쪽이면 극단 구간보다는 레벨 대응이 더 중요한 상태입니다."

    paragraph_1 = (
        f"{UNDERLYING_LABEL}는 현재 {_fmt_price(close)}로 1일 {_fmt_pct(ret_1d)}, 5일 {_fmt_pct(ret_5d)}, "
        f"1개월 {_fmt_pct(ret_1m)} 흐름을 보이고 있습니다. 가격은 120일 평균선({_fmt_price(ma120)}) 대비 "
        f"{_fmt_pct(ma120_gap)} 위치에 있고, 120일 평균 대비 Z-Score는 {_fmt_sigma(zscore)}로 "
        f"{z_state} 구간입니다. "
        f"{zscore_tone} "
        f"또한 AVWAP 대비 {_fmt_pct(avwap_gap)}, POC 대비 {_fmt_pct(poc_gap)} 수준이라는 점은 "
        "지금 가격대가 단순한 이탈 구간이 아니라 실제 거래가 누적된 밀집 구간 위에서 움직이고 있음을 뜻합니다. "
        f"포트폴리오 통계식 기준 20일 Volatility는 {_fmt_pct(volatility)}입니다."
    )

    top_strikes = [f"{float(v):.0f}" for v in oi_total["strike"].tolist()[:4]]
    strike_text = ", ".join(top_strikes) if top_strikes else "데이터 공백"
    if np.isnan(max_pain_gap):
        max_pain_text = "Max Pain 해석은 이번 데이터에서는 제한적입니다."
    elif abs(max_pain_gap) < 1.0:
        max_pain_text = (
            f"현물 가격이 Max Pain({_fmt_price(max_pain)})와 매우 가까워 만기 전 가격이 해당 구간에 붙는 핀 현상을 경계할 필요가 있습니다."
        )
    elif max_pain_gap > 0:
        max_pain_text = (
            f"현물 가격이 Max Pain({_fmt_price(max_pain)})를 {_fmt_pct(max_pain_gap)} 상회하고 있어 "
            "단기적으로는 상단에서 되돌림 압력이 걸릴 여지가 남아 있습니다."
        )
    else:
        max_pain_text = (
            f"현물 가격이 Max Pain({_fmt_price(max_pain)})를 {_fmt_pct(abs(max_pain_gap))} 밑돌고 있어 "
            "만기 접근 과정에서 상방 복귀 시도가 나올 수 있습니다."
        )

    if pcr_oi > 1.15 and pcr_vol > 1.15:
        hedge_text = "OI와 거래량 기준 Put/Call 비율이 모두 1을 웃돌아, 옵션 시장 참여자들은 상방 추격보다 하방 방어에 더 많은 비용을 지불하고 있습니다."
    elif pcr_oi < 0.9 and pcr_vol < 0.9:
        hedge_text = "OI와 거래량 기준 Put/Call 비율이 모두 낮아, 시장은 방어보다 상방 참여에 더 무게를 두는 모습입니다."
    else:
        hedge_text = "Put/Call 비율은 한쪽으로 과도하게 기울었다기보다, 방향 베팅과 헤지가 혼재된 상태로 읽는 편이 적절합니다."

    paragraph_2 = (
        f"옵션 포지셔닝에서는 OI 기준 Put/Call 비율이 {_fmt_ratio(pcr_oi)}, 거래량 기준이 {_fmt_ratio(pcr_vol)}로 집계됐습니다. "
        f"{hedge_text} OI가 많이 쌓인 스트라이크는 {strike_text}포인트 부근이며, 이는 단기적으로 "
        "호가가 자주 붙고 이탈 시 감마 반응이 커질 수 있는 가격대라는 뜻입니다. "
        f"{max_pain_text}"
    )

    short_iv = _safe_num(term_df.iloc[0]["atm_iv"]) if not term_df.empty else float("nan")
    long_iv = _safe_num(term_df.iloc[-1]["atm_iv"]) if not term_df.empty else float("nan")
    target_iv_30d = _compute_target_atm_iv(term_df, 30)
    iv_rv_gap = float("nan") if np.isnan(target_iv_30d) or np.isnan(volatility) else target_iv_30d - volatility

    if np.isnan(short_iv) or np.isnan(long_iv):
        iv_shape_text = "ATM IV 만기 구조를 충분히 읽기 어려워 변동성 해석은 보수적으로 접근해야 합니다."
    elif short_iv > long_iv + 1.0:
        iv_shape_text = (
            f"근월 ATM IV가 {short_iv:.2f}%로 원월 {long_iv:.2f}%보다 높아, 시장이 아주 가까운 일정에서 더 큰 이벤트 리스크를 반영하고 있습니다."
        )
    elif long_iv > short_iv + 1.0:
        iv_shape_text = (
            f"원월 ATM IV가 {long_iv:.2f}%로 더 높아, 단기 이벤트보다 중기 불확실성을 더 크게 가격에 반영하는 구조입니다."
        )
    else:
        iv_shape_text = (
            f"근월 ATM IV {short_iv:.2f}%와 원월 {long_iv:.2f}%의 차이가 크지 않아, 변동성 프리미엄은 전체 만기 구간에 비교적 고르게 퍼져 있습니다."
        )

    if np.isnan(iv_rv_gap):
        iv_rv_text = "실현변동성과 옵션 프리미엄의 상대 가격 비교는 제한적입니다."
    elif iv_rv_gap > 4.0:
        iv_rv_text = (
            f"30D IV가 최근 20일 Volatility {volatility:.2f}%보다 높아, 한 달 구간 옵션 프리미엄은 다소 비싸게 거래되고 있습니다."
        )
    elif iv_rv_gap < -2.0:
        iv_rv_text = (
            f"30D IV가 최근 20일 Volatility {volatility:.2f}%보다 낮아, 한 달 구간 옵션 프리미엄이 상대적으로 눌려 있는 편입니다."
        )
    else:
        iv_rv_text = (
            f"30D IV({target_iv_30d:.2f}%)와 최근 20일 Volatility({volatility:.2f}%) 사이 괴리가 크지 않아, 옵션 가격은 최근 실제 변동을 대체로 무난하게 반영하고 있습니다."
        )

    paragraph_3 = (
        f"{iv_shape_text} {iv_rv_text} "
        f"최근 ATR14가 {_fmt_price(atr14)}라는 점을 감안하면, 당일 방향을 맞히는 것만큼이나 "
        "하루 변동폭을 감당할 수 있는 포지션 크기와 손절 간격을 어떻게 잡느냐가 더 중요합니다."
    )

    if macro_stats:
        vix_curr = _safe_num(macro_stats.get("vix_curr"))
        dxy_corr = _safe_num(macro_stats.get("dxy_corr"))
        yield_corr = _safe_num(macro_stats.get("yield_corr"))
        rs_slope = _safe_num(macro_stats.get("rs_slope_20d"))
        macro_paragraph = (
            f"거시 배경에서는 VIX가 {_fmt_ratio(vix_curr)}로 {macro_stats.get('vix_status')} 국면에 있고, "
            f"달러와의 60일 상관은 {_fmt_ratio(dxy_corr)}, 10년물 금리와의 60일 상관은 {_fmt_ratio(yield_corr)}입니다. "
            f"{UNDERLYING_LABEL}/SPY 상대강도 변화가 {_fmt_pct(rs_slope)}라는 점은 나스닥 100 원지수가 광범위 시장 대비 어느 정도 주도력을 유지하고 있는지 보여줍니다. "
            f"여기에 내부 수급은 {smc_result['order_flow']}로 읽히고 AMD 국면 판정은 {smc_result['amd_phase']}이므로, "
            "현재 구간은 방향성 확신 하나로 밀어붙이기보다 가격 레벨과 옵션 수급이 만나는 지점을 따라가는 전략이 더 적합합니다."
        )
    else:
        macro_paragraph = (
            f"거시 보조 지표는 충분히 확보되지 않았지만, 내부 수급은 {smc_result['order_flow']}로 읽히고 "
            f"AMD 국면은 {smc_result['amd_phase']}으로 분류됩니다. 따라서 지금은 거대한 거시 서사보다 "
            "실제 체결이 쌓인 가격대와 옵션 포지셔닝의 변화를 우선해서 보는 편이 더 실무적입니다."
        )

    return [paragraph_1, paragraph_2, paragraph_3, macro_paragraph]


def _chart_fallback_html(title: str) -> str:
    return (
        "<div style='border:1px dashed #cbd5e1; border-radius:12px; padding:16px; "
        "margin:10px 0 16px; background:#f8fafc; color:#475569;'>"
        f"<strong>{html.escape(title)}</strong>"
        "<p style='margin:8px 0 0;'>"
        "plotly 패키지가 설치되어 있지 않아 차트는 생략하고 정량 요약과 표 중심으로 보고서를 생성했습니다."
        "</p></div>"
    )


def _build_trend_summary(curr: pd.Series, p1d: pd.Series, p1m: pd.Series, df_all: pd.DataFrame) -> dict[str, object]:
    close = _safe_num(curr.get("Close"))
    ma120 = _safe_num(curr.get("MA120"))
    p1m_ma120 = _safe_num(p1m.get("MA120"))
    zscore = _safe_num(curr.get("ZSCORE120"))
    supertrend_value = _safe_num(curr.get("SUPERTREND_10_3"))
    supertrend_dir = str(curr.get("SUPERTREND_10_3_DIR", "UNKNOWN"))
    supertrend_gap = _level_gap_pct(close, supertrend_value)

    long_trend = "BULL" if not np.isnan(ma120) and close > ma120 else "BEAR"
    short_trend = _zscore_state(zscore)
    divergence = _check_zscore_divergence(df_all)
    ma120_slope = (
        (ma120 / (p1m_ma120 + 1e-9) - 1) * 100
        if not np.isnan(ma120) and not np.isnan(p1m_ma120)
        else float("nan")
    )

    return {
        "long_trend": long_trend,
        "short_trend": short_trend,
        "divergence": divergence,
        "ma120_slope": ma120_slope,
        "zscore": zscore,
        "supertrend_dir": supertrend_dir,
        "supertrend_value": supertrend_value,
        "supertrend_gap": supertrend_gap,
    }


def _render_html(
    as_of: dt.datetime,
    out_path: Path,
    price_df: pd.DataFrame,
    vftw_snapshot_df: pd.DataFrame,
    vx_proxy_momentum_df: pd.DataFrame,
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
    target_iv_30d = _compute_target_atm_iv(term_df, 30)
    iv_rv_spread = target_iv_30d - _safe_num(curr.get("Volatility"))
    oi_expiry, oi_dte = _select_expiry_near_dte(opt_df, 30)
    if oi_expiry is None:
        oi_expiry = expiries[0]
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

    fallback_count = int(opt_df["iv_source"].eq("model_fallback").sum()) if "iv_source" in opt_df.columns else 0

    if HAS_PLOTLY:
        fig_price = _build_price_figure(price_df)
        fig_traded_value = _build_traded_value_figure(price_df)
        fig_zscore = _build_zscore_oscillator_figure(price_df)
        fig_vx_proxy_momentum = _build_vx_proxy_momentum_figure(vx_proxy_momentum_df)
        fig_oi = _build_oi_figure(opt_df, oi_expiry)
        fig_term = _build_term_structure_figure(
            term_df if not term_df.empty else pd.DataFrame({"dte": [], "atm_iv": [], "expiry": []})
        )
        fig_skew = _build_skew_figure(opt_df, spot, 30)
        price_div = plotly_to_html(fig_price, include_plotlyjs="cdn", full_html=False)
        traded_value_div = plotly_to_html(fig_traded_value, include_plotlyjs=False, full_html=False)
        zscore_div = plotly_to_html(fig_zscore, include_plotlyjs=False, full_html=False)
        vx_proxy_momentum_div = plotly_to_html(fig_vx_proxy_momentum, include_plotlyjs=False, full_html=False)
        oi_div = plotly_to_html(fig_oi, include_plotlyjs=False, full_html=False)
        term_div = plotly_to_html(fig_term, include_plotlyjs=False, full_html=False)
        skew_div = plotly_to_html(fig_skew, include_plotlyjs=False, full_html=False)
    else:
        price_div = _chart_fallback_html(f"{UNDERLYING_LABEL} 가격 추이")
        traded_value_div = _chart_fallback_html("거래액 추이")
        zscore_div = _chart_fallback_html("120일 Z-Score 오실레이터")
        vx_proxy_momentum_div = _chart_fallback_html("VX 곡선 모멘텀 프록시")
        oi_div = _chart_fallback_html("30D 근접 만기 OI 분포")
        term_div = _chart_fallback_html("ATM IV 만기 구조")
        skew_div = _chart_fallback_html(f"{UNDERLYING_LABEL} 30D 변동성 스큐")

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

    def _traded_value_t(row: pd.Series) -> float:
        value = _safe_num(row.get("Traded_Value"))
        return float("nan") if np.isnan(value) else value / 1e12

    indicator_metrics = [
        ("120D Z-Score (σ)", _v(curr, "ZSCORE120"), _v(p1d, "ZSCORE120"), _v(p1w, "ZSCORE120"), _v(p1m, "ZSCORE120")),
        ("AVWAP 괴리율 (%)", _avwap_gap(curr), _avwap_gap(p1d), _avwap_gap(p1w), _avwap_gap(p1m)),
        ("Volatility (%)", _v(curr, "Volatility"), _v(p1d, "Volatility"), _v(p1w, "Volatility"), _v(p1m, "Volatility")),
        ("30D IV (%)", target_iv_30d, float("nan"), float("nan"), float("nan")),
        ("IV-RV Spread (%)", iv_rv_spread, float("nan"), float("nan"), float("nan")),
        ("거래액 (조)", _traded_value_t(curr), _traded_value_t(p1d), _traded_value_t(p1w), _traded_value_t(p1m)),
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
    ma120_slope = _safe_num(trend_info.get("ma120_slope"))
    zscore_now = _safe_num(trend_info.get("zscore"))
    supertrend_dir = str(trend_info.get("supertrend_dir", "UNKNOWN"))
    supertrend_value = _safe_num(trend_info.get("supertrend_value"))
    supertrend_gap = _safe_num(trend_info.get("supertrend_gap"))
    avwap_now = _safe_num(curr.get("AVWAP"))
    vftw_latest = (
        vftw_snapshot_df.dropna(subset=["VFTW_HAPPINESS"]).iloc[-1]
        if not vftw_snapshot_df.empty and "VFTW_HAPPINESS" in vftw_snapshot_df.columns and not vftw_snapshot_df.dropna(subset=["VFTW_HAPPINESS"]).empty
        else pd.Series(dtype="float64")
    )
    proxy_latest = (
        vx_proxy_momentum_df.dropna(subset=["VX_PROXY_MOMENTUM"]).iloc[-1]
        if not vx_proxy_momentum_df.empty and "VX_PROXY_MOMENTUM" in vx_proxy_momentum_df.columns and not vx_proxy_momentum_df.dropna(subset=["VX_PROXY_MOMENTUM"]).empty
        else pd.Series(dtype="float64")
    )
    vftw_happiness_now = _safe_num(vftw_latest.get("VFTW_HAPPINESS"))
    vx1_now = _safe_num(vftw_latest.get("VX1"))
    vx2_now = _safe_num(vftw_latest.get("VX2"))
    proxy_momentum_now = _safe_num(proxy_latest.get("VX_PROXY_MOMENTUM"))
    vixy_now = _safe_num(proxy_latest.get("VIXY"))
    vixm_now = _safe_num(proxy_latest.get("VIXM"))

    report_lines: list[str] = [
        f"종합 점수: {composite_score:.1f}/100 | 현재 권장 포지션: [{status_text}]",
        f"120일 기준 추세: {trend_info['long_trend']} | Z-Score={_fmt_sigma(zscore_now)} ({trend_info['short_trend']}) | MA120 기울기(1M): {_fmt_pct(ma120_slope)}",
        f"수급 분석: Order Flow={smc_result['order_flow']} | AMD 국면={smc_result['amd_phase']}",
        f"모멘텀 점검: Z-Score 다이버전스 = {trend_info['divergence']} | Supertrend(10,3) = {supertrend_dir} ({_fmt_price(supertrend_value)}, 현재가 대비 {_fmt_pct(supertrend_gap)})",
    ]
    if not np.isnan(vftw_happiness_now):
        report_lines.append(
            f"VX 최신 스냅샷: ((VX1!/VX2!)-1)×-100 = {_fmt_delta(vftw_happiness_now)} | "
            f"{VFTW1_SYMBOL}={_fmt_ratio(vx1_now)}, {VFTW2_SYMBOL}={_fmt_ratio(vx2_now)}"
        )
    if not np.isnan(proxy_momentum_now):
        report_lines.append(
            f"VX 라인 프록시: ((VIXY/VIXM)-1)×-100 = {_fmt_delta(proxy_momentum_now)} | "
            f"VIXY={_fmt_ratio(vixy_now)}, VIXM={_fmt_ratio(vixm_now)}"
        )
    if smc_result.get("sweep_low"):
        report_lines.append("유동성 Sweep Low 신호가 감지되어 단기 반등 시도를 체크할 구간입니다.")
    if smc_result.get("sweep_high"):
        report_lines.append("유동성 Sweep High 신호가 감지되어 고점 돌파 실패 리스크를 주의해야 합니다.")
    if not np.isnan(poc_price):
        report_lines.append(f"가격 방어선: POC(최대 매물대) = {_fmt_price(poc_price)}")
    if not np.isnan(avwap_now):
        report_lines.append(f"거래량 가중 평균 레벨(AVWAP): {_fmt_price(avwap_now)}")
    if not np.isnan(max_pain):
        report_lines.append(f"옵션 집중 가격(Max Pain): {_fmt_price(max_pain)}")
    report_html = "".join([f"<li>{html.escape(line)}</li>" for line in report_lines])

    if macro_stats:
        macro_lines = [
            f"달러 인덱스(DXY): {_fmt_ratio(_safe_num(macro_stats['dollar_idx']))} | {UNDERLYING_LABEL} 상관(60D): {_fmt_ratio(_safe_num(macro_stats['dxy_corr']))}",
            f"미 10년물(^TNX): {_fmt_pct(_safe_num(macro_stats['yield_10y']))} | {UNDERLYING_LABEL} 상관(60D): {_fmt_ratio(_safe_num(macro_stats['yield_corr']))}",
            f"반도체(SOXX) 상관(60D): {_fmt_ratio(_safe_num(macro_stats['soxx_corr']))}",
            f"VIX 레짐: {_fmt_ratio(_safe_num(macro_stats['vix_curr']))} ({macro_stats['vix_status']})",
            f"{UNDERLYING_LABEL}/SPY 상대강도 변화(20D): {_fmt_pct(_safe_num(macro_stats['rs_slope_20d']))}",
        ]
    else:
        macro_lines = ["거시 보조 지표를 충분히 수집하지 못해 기술/옵션 신호 중심으로 해석했습니다."]
    macro_html = "".join([f"<li>{html.escape(line)}</li>" for line in macro_lines])

    interpretation_paragraphs = _build_data_interpretation_paragraphs(
        curr=curr,
        pcr_oi=float(pcr_oi),
        pcr_vol=float(pcr_vol),
        max_pain=max_pain,
        term_df=term_df,
        oi_total=oi_total,
        macro_stats=macro_stats,
        trend_info=trend_info,
        smc_result=smc_result,
        poc_price=poc_price,
        avwap_now=avwap_now,
    )
    interpretation_html = "".join(
        [f"<p>{html.escape(paragraph)}</p>" for paragraph in interpretation_paragraphs]
    )

    conclusion_html = "".join([f"<li>{html.escape(line)}</li>" for line in conclusion_lines])
    iv_note_parts = []
    if fallback_count:
        iv_note_parts.append(f"단기 Yahoo IV 품질 이슈로 {fallback_count:,}개 계약은 옵션 가격 기반 추정 IV로 보정")
    else:
        iv_note_parts.append("Yahoo 원시 IV를 사용")
    if not HAS_PLOTLY:
        iv_note_parts.append("plotly 미설치로 차트는 생략")
    iv_note = " | ".join(iv_note_parts)

    html_doc = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>나스닥 옵션 분석 ({UNDERLYING_LABEL})</title>
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
    .prose p {{
      margin: 0 0 14px;
      font-size: 15px;
      color: #1e293b;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>나스닥 옵션 분석 ({UNDERLYING_LABEL})</h1>
      <p class="meta">as of (KST): {as_of.strftime("%Y-%m-%d %H:%M:%S")}</p>
      <p class="meta">데이터 상태: yfinance 기준 최근 체결/전일 종가 혼합 (지연 가능)</p>
      <p class="meta">IV 처리: {html.escape(iv_note)}</p>
      <p class="meta">파일: {html.escape(str(out_path))}</p>
      <div class="grid">
        <div class="metric"><div class="label">{UNDERLYING_LABEL} 현재가</div><div class="value">{_fmt_price(_safe_num(curr.get("Close")))}</div></div>
        <div class="metric"><div class="label">1D 변화율</div><div class="value">{_fmt_pct(_safe_num(curr.get("RET_1D")))}</div></div>
        <div class="metric"><div class="label">5D 변화율</div><div class="value">{_fmt_pct(_safe_num(curr.get("RET_5D")))}</div></div>
        <div class="metric"><div class="label">1M 변화율</div><div class="value">{_fmt_pct(_safe_num(curr.get("RET_1M")))}</div></div>
        <div class="metric"><div class="label">120D Z-Score</div><div class="value">{_fmt_sigma(_safe_num(curr.get("ZSCORE120")))}</div></div>
        <div class="metric"><div class="label">Volatility</div><div class="value">{_fmt_pct(_safe_num(curr.get("Volatility")))}</div></div>
        <div class="metric"><div class="label">30D IV</div><div class="value">{_fmt_pct(target_iv_30d)}</div></div>
        <div class="metric"><div class="label">IV-RV Spread</div><div class="value">{_fmt_pct(iv_rv_spread)}</div></div>
        <div class="metric"><div class="label">VX Snapshot</div><div class="value">{_fmt_delta(vftw_happiness_now)}</div></div>
        <div class="metric"><div class="label">VX Proxy</div><div class="value">{_fmt_delta(proxy_momentum_now)}</div></div>
        <div class="metric"><div class="label">거래액</div><div class="value">{_fmt_price(_safe_num(curr.get("Traded_Value")) / 1e12)}조</div></div>
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
      {traded_value_div}
      {zscore_div}
      {vx_proxy_momentum_div}
    </section>

    <section class="card">
      <h2>2. 옵션체인 핵심</h2>
      <h3>2.1 30D 근접 만기 OI 분포</h3>
      {oi_div}
      <h3>2.2 ATM IV 만기 구조</h3>
      {term_div}
      <h3>2.3 30D 변동성 스큐</h3>
      {skew_div}
    </section>

    <section class="card">
      <h2>3. {UNDERLYING_LABEL} 실시간 지표 요약</h2>
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
      <h2>5. 데이터 해석</h2>
      <div class="prose">{interpretation_html}</div>
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
    p = argparse.ArgumentParser(description=f"{UNDERLYING_LABEL} 나스닥 옵션 분석 HTML 리포트 생성기")
    p.add_argument("--period", default="2y", help="가격 히스토리 기간 (기본: 2y)")
    p.add_argument("--max-exp", type=int, default=20, help="수집할 옵션 만기 개수 (기본: 20, 30D 분석용)")
    p.add_argument(
        "--strike-band",
        type=float,
        default=0.12,
        help="현물 대비 스트라이크 필터 비율 (기본: 0.12 = ±12%%)",
    )
    p.add_argument("--outdir", default="reports", help="출력 디렉터리 (기본: reports)")
    return p.parse_args()


def main() -> int:
    _ensure_supported_runtime()
    args = _parse_args()
    as_of = _now_kst()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"nasdaq_option_analysis_{REPORT_SLUG}_{as_of.strftime('%Y%m%d_%H%M%S')}_kst"
    out_path = outdir / f"{stem}.html"

    price_df = _prepare_price_data(args.period)
    vftw_snapshot_df = _prepare_vftw_snapshot_data()
    vx_proxy_momentum_df = _prepare_vx_proxy_momentum_data(args.period)
    opt_df, expiries, spot = _fetch_option_data(args.max_exp, args.strike_band)

    html_doc = _render_html(
        as_of=as_of,
        out_path=out_path,
        price_df=price_df,
        vftw_snapshot_df=vftw_snapshot_df,
        vx_proxy_momentum_df=vx_proxy_momentum_df,
        opt_df=opt_df,
        expiries=expiries,
        spot=spot,
    )
    out_path.write_text(html_doc, encoding="utf-8")

    print(f"saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
