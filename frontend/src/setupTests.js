// src/setupTests.js
import '@testing-library/jest-dom';

// Полифилл для clearImmediate / setImmediate
global.setImmediate = (fn, ...args) => setTimeout(fn, 0, ...args);
global.clearImmediate = (id) => clearTimeout(id);