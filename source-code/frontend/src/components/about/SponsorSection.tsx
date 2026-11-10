import { useTranslation } from 'react-i18next'
import { Heart } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { cn } from '@/lib/utils'

interface SponsorSectionProps {
  className?: string
}

export function SponsorSection({ className }: SponsorSectionProps) {
  const { t } = useTranslation()

  return (
    <Card className={cn('flex h-full flex-col p-5', className)}>
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-foreground">
        <Heart className="size-4 text-danger" />
        {t('about.sponsor.title')}
      </h2>
      <div className="flex flex-1 flex-col items-center justify-center">
        <img
          src="/qr/sponsor-qr.png"
          alt="Sponsor QR Code"
          className="mb-4 size-32 rounded-md object-cover"
        />
        <div className="text-center text-sm text-muted-foreground leading-relaxed space-y-1">
          <p>{t('about.sponsor.line1')}</p>
          <p>{t('about.sponsor.line2')}</p>
        </div>
      </div>
    </Card>
  )
}

export default SponsorSection