const {test}=require('node:test'),assert=require('node:assert/strict');
const {simulateWinProbability,gammaRemaining,simulationRandom}=require('../projections.js');
const pre=mean=>({actual:0,initialProjection:mean,state:'pre'});
const final=actual=>({actual,state:'post'});
test('gamma shape 2 draws have specified mean and variance',()=>{
 const r=simulationRandom(321);let sum=0,squares=0;const n=100000;
 for(let i=0;i<n;i++){const x=gammaRemaining(10,r);sum+=x;squares+=x*x;assert.ok(x>=0);}
 assert.ok(Math.abs(sum/n-10)<0.1);assert.ok(Math.abs(squares/n-(sum/n)**2-50)<1.5);
});
test('20K simulations match analytical gamma comparisons and are repeatable',()=>{
 const p=simulateWinProbability([pre(20)],[pre(10)]);
 assert.equal(p.simulations,20000);assert.ok(Math.abs(p.west-20/27)<0.015);
 assert.equal(p.west+p.east+p.tie,1);
 assert.deepEqual(p,simulateWinProbability([pre(20)],[pre(10)]));
 assert.ok(Math.abs(simulateWinProbability([pre(10)],[pre(10)]).west-0.5)<0.015);
});
test('actual points are fixed and final games and ties resolve exactly',()=>{
 assert.equal(simulateWinProbability([final(10)],[final(9)]).west,1);
 assert.equal(simulateWinProbability([final(10)],[final(10)]).tie,1);
 const p=simulateWinProbability([final(10)],[pre(10)]);
 assert.ok(Math.abs(p.west-(1-3*Math.exp(-2)))<0.015);
 assert.equal(simulateWinProbability([pre(0)],[final(1)]).east,1);
});
test('remaining mean uses the live clock; missing data stays unavailable',()=>{
 const half={actual:0,initialProjection:20,state:'in',timeRemainingFraction:0.5};
 assert.deepEqual(simulateWinProbability([half],[pre(10)]),simulateWinProbability([pre(10)],[pre(10)]));
 assert.equal(simulateWinProbability([null],[pre(10)]),null);
 assert.equal(simulateWinProbability([{actual:1,initialProjection:10,state:'in'}],[pre(10)]),null);
});
