import { useTranslation } from 'react-i18next'
import { Users } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { cn } from '@/lib/utils'

interface TelegramSectionProps {
  className?: string
}

const TELEGRAM_GROUP_URL = 'https://t.me/+BPXW6b_jvlxkOTMx'

export function TelegramSection({ className }: TelegramSectionProps) {
  const { t } = useTranslation()

  const handleJoinGroup = () => {
    window.open(TELEGRAM_GROUP_URL, '_blank', 'noopener,noreferrer')
  }

  return (
    <Card className={cn('flex h-full flex-col p-5', className)}>
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-foreground">
        <Users className="size-4 text-info" />
        {t('about.telegram.title')}
      </h2>
      <div className="flex flex-1 flex-col items-center justify-center">
        <img
          src="/qr/tg-qr.png"
          alt="Telegram Group QR Code"
          className="mb-4 size-32 rounded-md object-cover"
        />
        <Button
          variant="outline"
          size="sm"
          onClick={handleJoinGroup}
          className="gap-2"
        >
          <img src="/icons/tg-icon.png" alt="Telegram" className="size-4" />
          {t('about.telegram.joinButton')}
        </Button>
      </div>
    </Card>
  )
}

export default TelegramSection