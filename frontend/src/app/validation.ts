import { z } from "zod";

// Disable Zod's eval probe before constructing schemas under the strict CSP.
z.config({ jitless: true });
