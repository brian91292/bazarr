import { vi } from "vitest";
import { setAuthenticated, setCriticalError, setOnlineStatus } from "./event";

describe("event utilities", () => {
  it("setAuthenticated should dispatch app-auth-changed event", () => {
    const spy = vi.fn();
    window.addEventListener("app-auth-changed", spy);
    setAuthenticated(true);
    expect(spy).toHaveBeenCalled();
    const event = spy.mock.calls[0][0] as CustomEvent;
    expect(event.detail).toEqual({ authenticated: true });
  });

  it("setCriticalError should dispatch app-critical-error event", () => {
    const spy = vi.fn();
    window.addEventListener("app-critical-error", spy);
    setCriticalError("Error message");
    expect(spy).toHaveBeenCalled();
    const event = spy.mock.calls[0][0] as CustomEvent;
    expect(event.detail).toEqual({ message: "Error message" });
  });

  it("setOnlineStatus should dispatch app-online-status event", () => {
    const spy = vi.fn();
    window.addEventListener("app-online-status", spy);
    setOnlineStatus(false);
    expect(spy).toHaveBeenCalled();
    const event = spy.mock.calls[0][0] as CustomEvent;
    expect(event.detail).toEqual({ online: false });
  });
});
