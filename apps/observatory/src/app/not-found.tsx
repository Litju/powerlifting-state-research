import Link from "next/link";
import { PageHeader } from "@/components/Ui";
import ui from "@/components/ui.module.css";

export default function NotFound() {
  return (
    <div className={ui.page}>
      <PageHeader eyebrow="404" title="This page is not part of the Observatory">
        <p>
          Return to the <Link href="/">Observatory</Link>, the <Link href="/forecast">forecasting lab</Link> or the <Link href="/journey">research journey</Link>.
        </p>
      </PageHeader>
    </div>
  );
}
