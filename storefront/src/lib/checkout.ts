type CheckoutResult = {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
};
type Order = { key_id: string; order_id: string; amount: number; currency: "INR" };
type CheckoutOptions = {
  key: string; order_id: string; amount: number; currency: string;
  handler: (result: CheckoutResult) => void;
  modal: { ondismiss: () => void };
};
declare global {
  interface Window {
    Razorpay?: new (options: CheckoutOptions) => { open: () => void };
  }
}

let loading: Promise<void> | undefined;
export function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  if (loading) return loading;
  loading = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    const timer = window.setTimeout(() => fail(), 15000);
    function fail() {
      window.clearTimeout(timer);
      script.remove();
      loading = undefined;
      reject(new Error("Checkout could not load. Please retry."));
    }
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => {
      window.clearTimeout(timer);
      if (window.Razorpay) resolve(); else fail();
    };
    script.onerror = fail;
    document.head.appendChild(script);
  });
  return loading;
}

export async function checkout(order: Order): Promise<CheckoutResult | null> {
  await loadCheckout();
  if (!order.key_id.startsWith("rzp_test_") || !window.Razorpay) {
    throw new Error("Test Mode checkout is unavailable.");
  }
  const Razorpay = window.Razorpay;
  return new Promise((resolve) => {
    new Razorpay({
      key: order.key_id, order_id: order.order_id, amount: order.amount,
      currency: order.currency, handler: resolve, modal: { ondismiss: () => resolve(null) },
    }).open();
  });
}
