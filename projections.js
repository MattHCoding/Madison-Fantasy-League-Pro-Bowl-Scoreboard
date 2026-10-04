'use strict';
function pointsRemainingFraction(timeRemaining, exponent = 1) {
  if (!Number.isFinite(timeRemaining) || !Number.isFinite(exponent) || exponent <= 0) return null;
  return Math.pow(Math.max(0,Math.min(1,timeRemaining)),exponent);
}
function projectedPoints(score, exponent = 1) {
  if (!score || !Number.isFinite(score.actual)) return null;
  if (score.state === 'post' || score.state === 'bye') return score.actual;
  const remaining = score.state === 'pre' ? 1 : score.timeRemainingFraction;
  if (remaining === 0) return score.actual;
  if (!Number.isFinite(remaining) || !Number.isFinite(score.initialProjection)) return null;
  const fraction = pointsRemainingFraction(remaining,exponent);
  return fraction === null ? null : score.actual + fraction * score.initialProjection;
}

const WIN_SIMULATIONS = 20000;
function simulationRandom(seed = 20261004) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t ^= t + Math.imul(t ^ t >>> 7, 61 | t);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function gammaRemaining(mean, random) {
  if (mean === 0) return 0;
  // Shape 2 is the sum of two independent unit-rate exponentials.
  const draw = -Math.abs(mean) / 2 * (Math.log(1 - random()) + Math.log(1 - random()));
  return mean < 0 ? draw + 2 * mean : draw;
}
function simulateWinProbability(west, east, exponent = 1) {
  if (!west.length || !east.length) return null;
  const sides = [west, east].map(rows => rows.map(score => {
    const projected = projectedPoints(score,exponent);
    return projected === null ? null : {actual:score.actual,mean:projected-score.actual};
  }));
  if (sides.flat().some(p => !p || !Number.isFinite(p.mean))) return null;
  const actualMargin = sides[0].reduce((sum,p)=>sum+p.actual,0) - sides[1].reduce((sum,p)=>sum+p.actual,0);
  const remaining = sides.flatMap((players,side)=>players.filter(p=>p.mean!==0).map(p=>({mean:p.mean,sign:side===0?1:-1})));
  const random = simulationRandom(); // Stable results when the same score data is refreshed.
  let westWins=0,eastWins=0,ties=0;
  for (let trial=0;trial<WIN_SIMULATIONS;trial++) {
    let margin=actualMargin;
    for (const player of remaining) margin += player.sign * gammaRemaining(player.mean,random);
    if (margin > 1e-9) westWins++;
    else if (margin < -1e-9) eastWins++;
    else ties++;
  }
  return {west:westWins/WIN_SIMULATIONS,east:eastWins/WIN_SIMULATIONS,tie:ties/WIN_SIMULATIONS,simulations:WIN_SIMULATIONS};
}
if (typeof module !== 'undefined') module.exports = {pointsRemainingFraction,projectedPoints,simulateWinProbability,gammaRemaining,simulationRandom};
