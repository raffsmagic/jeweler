# Security

Jewel decides which copied texts an app treats as secret, so a bypass (a real password
shape that scores low), a crash, or a slowdown on hostile input is a security bug.

Please report it privately through GitHub: **Security → Report a vulnerability** on this
repository. Don't open a public issue, and don't include a real password, key or token in
a report: describe its shape (a = lower, A = upper, 9 = digit, symbols kept) instead.

The runtime has no dependencies and makes no network calls. The models are plain JSON
(weights only); `parseJewel` validates one loaded from anywhere other than this package.
