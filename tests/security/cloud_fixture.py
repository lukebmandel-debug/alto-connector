"""alto-cloud.js as the browser tests serve it: a demo config, and the Firebase
emulators. Usage: python cloud_fixture.py OUT_FILE SDK_VERSION"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from alto.cloud import emit_cloud_js   # noqa: E402

src = emit_cloud_js({"apiKey": "demo-key", "authDomain": "127.0.0.1",
                     "projectId": "demo-alto-security", "appId": "demo"})
v = "  const V = '"
i = src.index(v)
src = src[:i] + v + sys.argv[2] + src[src.index("';", i):]
hook = "  const db   = getFirestore(app);\n"
assert src.count(hook) == 1
src = src.replace(hook, hook + """  {
    const A = await import(`https://www.gstatic.com/firebasejs/${V}/firebase-auth.js`);
    const F = await import(`https://www.gstatic.com/firebasejs/${V}/firebase-firestore.js`);
    A.connectAuthEmulator(auth, 'http://127.0.0.1:9099', { disableWarnings: true });
    F.connectFirestoreEmulator(db, '127.0.0.1', 8080);
    window.__test = { signIn: (sub, email) => A.signInWithCredential(auth,
      A.GoogleAuthProvider.credential(JSON.stringify({ sub, email, email_verified: true }))) };
  }
""")
Path(sys.argv[1]).write_text(src, encoding="utf-8")
