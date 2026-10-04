'use strict';
function projectedPoints(score) {
  if (!score || !Number.isFinite(score.actual)) return null;
  if (score.state === 'post' || score.state === 'bye') return score.actual;
  const remaining = score.state === 'pre' ? 1 : score.timeRemainingFraction;
  if (remaining === 0) return score.actual;
  if (!Number.isFinite(remaining) || !Number.isFinite(score.initialProjection)) return null;
  return score.actual + Math.max(0,Math.min(1,remaining)) * score.initialProjection;
}
if (typeof module !== 'undefined') module.exports = {projectedPoints};
