import type { Metadata } from 'next';
import './globals.scss';
import { RunProvider } from '@/components/RunProvider';
import { Shell } from '@/components/Shell';

export const metadata: Metadata = {
  title: 'Choke Point',
  description:
    'Which single points of failure in a bill of materials would actually ' +
    'stop production, and how badly.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      {/* g10 for the whole document, so the tokens outside React's tree
          (html, body, the scroll gutter) match the tokens inside it. */}
      <body className="cds--g10">
        <RunProvider>
          <Shell>{children}</Shell>
        </RunProvider>
      </body>
    </html>
  );
}
