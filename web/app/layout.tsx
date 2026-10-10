import type { Metadata } from "next";
import { Open_Sans, STIX_Two_Text } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

const openSans = Open_Sans({
  variable: "--font-open-sans",
  subsets: ["latin"],
});

const stix = STIX_Two_Text({
  variable: "--font-stix",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "EMR workspace",
  description: "Synthetic EMR demo. The agent proposes; the doctor approves.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${openSans.variable} ${stix.variable} h-full antialiased`}>
      <body className="h-full overflow-hidden">
        <TooltipProvider delay={300}>{children}</TooltipProvider>
      </body>
    </html>
  );
}
