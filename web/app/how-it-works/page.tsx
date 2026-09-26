import type { Metadata } from 'next';
import { howItWorksHtml } from './content';

export const metadata: Metadata = {
  title: 'How It Works',
  description:
    'The pipeline, the verdicts, the tech stack, and the honest limits behind S.H.O.A.V.’s deterministic ingress and egress filters.',
};

export default function HowItWorksPage() {
  return <div dangerouslySetInnerHTML={{ __html: howItWorksHtml }} />;
}
