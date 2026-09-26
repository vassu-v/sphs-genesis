import { homeHtml } from './home-content';

export default function HomePage() {
  return <div dangerouslySetInnerHTML={{ __html: homeHtml }} />;
}
