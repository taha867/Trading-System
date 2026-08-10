export function toMoney(value) {
  const num = Number(value);
  return Number.isNaN(num) ? 0 : Math.round(num * 100) / 100;
}

// Mirrors backend/src/purchasing/service.py + schemas.py's two-stage rounding:
// rate_pkr is snapshotted/rounded once, then amount_pkr rounds qty × that
// already-rounded rate — not qty × rate_rmb × exchangeRate in one shot, which
// would silently drift from the server's total on any >2dp exchange rate.
export function computeRatePkr(rateRmb, exchangeRate) {
  return toMoney(Number(rateRmb) * Number(exchangeRate));
}

export function computeRmbAmount(qty, rateRmb) {
  return toMoney(Number(qty) * Number(rateRmb));
}

export function computePkrAmount(qty, rateRmb, exchangeRate) {
  return toMoney(Number(qty) * computeRatePkr(rateRmb, exchangeRate));
}

// Mirrors backend/src/cargo/service.py's create_shipment allocation math (phase-2-
// frontend spec §8.1): proportional split by basis value, remainder-corrected on the
// last line (ordered by ascending id) so allocated amounts always sum to the total.
export function computeCargoAllocation({ lines, basisValues, totalCostPkr }) {
  const total = Number(totalCostPkr);
  const ordered = [...lines].sort((a, b) => a.id - b.id);
  const totalBasis = ordered.reduce((sum, line) => sum + Number(basisValues[line.id] ?? 0), 0);
  if (!total || !totalBasis) return {};

  let allocatedSoFar = 0;
  const result = {};
  ordered.forEach((line, index) => {
    const isLast = index === ordered.length - 1;
    const allocatedCostPkr = isLast
      ? toMoney(total - allocatedSoFar)
      : toMoney((total * Number(basisValues[line.id] ?? 0)) / totalBasis);
    if (!isLast) allocatedSoFar += allocatedCostPkr;
    result[line.id] = {
      allocatedCostPkr,
      landedCostPkr: toMoney(Number(line.rate_pkr) + allocatedCostPkr / Number(line.qty)),
    };
  });
  return result;
}

// Mirrors backend/src/sales/schemas.py's SalesOrderLineRead.amount_pkr exactly:
// qty × rate_pkr, entered directly in PKR with no exchange-rate step — unlike
// purchasing, wholesale sales are quoted in PKR to begin with (backend spec §3.1).
export function computeSaleAmount(qty, ratePkr) {
  return toMoney(Number(qty) * Number(ratePkr));
}

export function formatRMB(value) {
  return `¥${Number(value).toFixed(2)}`;
}

export function formatPKR(value) {
  return `₨${Number(value).toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
