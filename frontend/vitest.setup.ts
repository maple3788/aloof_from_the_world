import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);

// jsdom does not implement scrollIntoView; MessageList calls it on new messages.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {});
