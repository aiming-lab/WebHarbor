// Pure renderer regression checks; no browser task evidence is fabricated here.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
function element() {
  return {children: [], dataset: {}, style: {}, className: '',
    classList: {add() {}}, addEventListener() {},
    appendChild(child) {this.children.push(child);}};
}
const context = {window: {CHESS_STATIC: '/static'}, document: {createElement: element}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/board.js'), 'utf8'), context);
const Board = context.window.ChessBoard;
test('white and black perspectives have the correct files, ranks and square colors', () => {
  for (const [flip, first, last] of [[false, 'a8', 'h1'], [true, 'h1', 'a8']]) {
    const container = element(); const board = new Board(container, {flip});
    assert.equal(container.children[0].dataset.sq, first);
    assert.equal(container.children[63].dataset.sq, last);
    assert.match(board.squares.a8.className, /light/);
    assert.match(board.squares.a1.className, /dark/);
  }
});
test('both pawn colors promote to a queen by default and preserve explicit underpromotion', () => {
  for (const [fen, from, to, expected, promo] of [
    ['7k/P7/8/8/8/8/8/7K w - - 0 1', 'a7', 'a8', 'Q'],
    ['7k/8/8/8/8/8/p7/7K b - - 0 1', 'a2', 'a1', 'q'],
    ['7k/P7/8/8/8/8/8/7K w - - 0 1', 'a7', 'a8', 'N', 'N'],
  ]) {
    const board = new Board(element(), {fen}); board.applyMove(from, to, promo);
    assert.equal(board.state.squares[to], expected); assert.equal(board.state.squares[from], undefined);
  }
});
