import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(cleanup)

// jsdom lacks the browser's modal API; native focus trapping/Escape are also
// verified in Chrome. Keep the open state faithful for accessible queries.
HTMLDialogElement.prototype.showModal ??= function () { this.open = true }
HTMLDialogElement.prototype.close ??= function () { this.open = false }
