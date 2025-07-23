// main.js – Einfaches Toggle-Menü für Mobile
document.addEventListener('DOMContentLoaded', function() {
  var menuToggle = document.getElementById('menu-toggle');
  var navLinks = document.querySelector('.nav-links');

  menuToggle.addEventListener('click', function() {
    // Beim Klick die Klasse "open" toggeln, um das Menü ein/auszublenden
    navLinks.classList.toggle('open');
  });
});
