<?php

namespace App\Notifications;

use Illuminate\Notifications\Notification;
use Illuminate\Notifications\Messages\MailMessage;

class MobileEmailChangedNotice extends Notification
{
    public function __construct(private string $newEmail) {}

    public function via(object $notifiable): array
    {
        return ['mail'];
    }

    public function toMail(object $notifiable): MailMessage
    {
        return (new MailMessage)
            ->subject('PlateTag — Your Email Address Was Changed')
            ->greeting('Hello,')
            ->line('The email address on your PlateTag account was changed to: **' . $this->newEmail . '**')
            ->line('If you made this change, no action is needed.')
            ->line('If you did **not** make this change, your account may be compromised. Please contact us immediately at support@platetag.app so we can restore your account.');
    }
}
