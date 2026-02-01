import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
    title: "Michael - Personal AI Assistant",
    description: "24/7 Personal AI Assistant with AG-UI + A2UI",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="ko">
            <body>{children}</body>
        </html>
    );
}
