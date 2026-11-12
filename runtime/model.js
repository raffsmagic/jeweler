// The built-in model: the newest models/jeweler-v<n>.json. In dist/ the build replaces this file
// with the bundled module; test/jewel.test.ts checks it is the newest.
import model from "../models/jeweler-v1.json" with { type: "json" };
export default model;
