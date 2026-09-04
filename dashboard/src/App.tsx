import { ArrowRight, LockKeyhole, Sparkles } from 'lucide-react'

function App() {
  return (
    <main className="grid min-h-svh bg-[#f4f7f5] lg:grid-cols-[1.05fr_0.95fr]">
      <section className="hidden bg-[#123c2d] p-14 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3 text-lg font-bold">
          <span className="grid size-11 place-items-center rounded-2xl bg-[#f2a92f] text-[#123c2d]">
            <Sparkles size={21} aria-hidden="true" />
          </span>
          Take-India
        </div>
        <div className="max-w-xl">
          <p className="mb-5 text-sm font-semibold uppercase tracking-[0.2em] text-[#9bd0b8]">
            Merchant workspace
          </p>
          <h1 className="text-5xl font-bold leading-[1.08] tracking-[-0.04em]">
            Run every booking mode from one calm workspace.
          </h1>
          <p className="mt-6 text-lg leading-8 text-[#c8ded3]">
            Configure services, staff, opening hours, classes and custom-order intake without a complicated setup.
          </p>
        </div>
        <p className="text-sm text-[#9bd0b8]">Phase 1 · Booking engine configuration</p>
      </section>

      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md rounded-3xl border border-[#dce4df] bg-white p-7 shadow-[0_24px_80px_rgba(18,60,45,0.09)] sm:p-10">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="grid size-10 place-items-center rounded-xl bg-[#123c2d] text-white">
              <Sparkles size={19} aria-hidden="true" />
            </span>
            <span className="font-bold">Take-India</span>
          </div>
          <span className="mb-5 grid size-12 place-items-center rounded-2xl bg-[#edf6f1] text-[#176848]">
            <LockKeyhole size={21} aria-hidden="true" />
          </span>
          <h2 className="text-3xl font-bold tracking-[-0.035em]">Welcome back</h2>
          <p className="mt-2 text-base leading-7 text-[#66736c]">
            Sign in to manage your storefront and availability.
          </p>
          <form className="mt-8 space-y-5">
            <label className="block text-sm font-semibold">
              Email address
              <input
                type="email"
                className="mt-2 h-12 w-full rounded-xl border border-[#ccd8d1] px-4 outline-none transition focus:border-[#176848] focus:ring-3 focus:ring-[#176848]/10"
                placeholder="owner@example.com"
              />
            </label>
            <label className="block text-sm font-semibold">
              Password
              <input
                type="password"
                className="mt-2 h-12 w-full rounded-xl border border-[#ccd8d1] px-4 outline-none transition focus:border-[#176848] focus:ring-3 focus:ring-[#176848]/10"
                placeholder="Enter your password"
              />
            </label>
            <button
              type="submit"
              className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#176848] font-semibold text-white transition hover:bg-[#12563c]"
            >
              Sign in <ArrowRight size={18} aria-hidden="true" />
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-[#66736c]">
            New to Take-India?{' '}
            <button className="font-semibold text-[#176848]">Create your merchant account</button>
          </p>
        </div>
      </section>
    </main>
  )
}

export default App

