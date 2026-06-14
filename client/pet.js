/** 像素吉祥物 — 类型 + 状态管理 */
var _petCurrentType = 'robot';

function setPetType(type) {
  var pet = document.getElementById('pet');
  if (!pet) return;
  pet.classList.remove('type-robot', 'type-cat', 'type-dog', 'type-alien');
  pet.classList.add('type-' + type);
  _petCurrentType = type;
}

function setPetState(state) {
  var pet = document.getElementById('pet');
  if (!pet) return;
  pet.classList.remove('idle', 'listening', 'processing', 'speaking');
  if (state) pet.classList.add(state);
}
