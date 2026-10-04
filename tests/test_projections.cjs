const {test}=require('node:test');
const assert=require('node:assert/strict');
const {projectedPoints}=require('../projections.js');
test('pregame, halftime and final forecasts use the player game clock',()=>{
 assert.equal(projectedPoints({actual:0,initialProjection:20,state:'pre'}),20);
 assert.equal(projectedPoints({actual:12,initialProjection:20,state:'in',timeRemainingFraction:0.5}),22);
 assert.equal(projectedPoints({actual:12,initialProjection:20,state:'post'}),12);
 assert.equal(projectedPoints({actual:-2,initialProjection:null,state:'post'}),-2);
 assert.equal(projectedPoints({actual:0,initialProjection:20,state:'bye'}),0);
 assert.equal(projectedPoints({actual:12,initialProjection:null,state:'in',timeRemainingFraction:0}),12);
});
test('missing scores, missing live clocks and missing baselines stay unknown',()=>{
 assert.equal(projectedPoints(null),null);
 assert.equal(projectedPoints({actual:null,initialProjection:20,state:'pre'}),null);
 assert.equal(projectedPoints({actual:12,initialProjection:20,state:'in'}),null);
 assert.equal(projectedPoints({actual:12,initialProjection:null,state:'in',timeRemainingFraction:0.5}),null);
});
