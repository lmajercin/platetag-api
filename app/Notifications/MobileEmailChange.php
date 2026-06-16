<?php
namespace App\Notifications;

use Illuminate\Bus\Queueable;
use Illuminate\Notifications\Messages\MailMessage;
use Illuminate\Notifications\Notification;

class MobileEmailChange extends Notification
{
    use Queueable;

    public function __construct(public readonly string $otp) {}

    public function via(object $notifiable): array
    {
        return ['mail'];
    }

    public function toMail(object $notifiable): MailMessage
    {
        return (new MailMessage)
            ->subject('PlateTag - Verify Your New Email Address')
            ->greeting('Hello!')
            ->line('Use this 6-digit code to confirm your new email address in the PlateTag app.')
            ->line('# ' . $this->otp)
            ->line('This code expires in 30 minutes.')
            ->line('If you did not request this change, your account is safe — no action is needed.')
            ->salutation('The PlateTag Team');
    }
}
