<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Models\SystemSetting;
use Illuminate\Database\Seeder;

class SystemSettingsSeeder extends Seeder
{
    public function run(): void
    {
        $settings = [
            [
                'key'         => 'app_name',
                'value'       => env('APP_NAME', 'Head Office Attendance System'),
                'type'        => 'string',
                'group'       => 'general',
                'label'       => 'Application Name',
                'is_public'   => true,
            ],
            [
                'key'         => 'timezone',
                'value'       => 'Asia/Manila',
                'type'        => 'string',
                'group'       => 'general',
                'label'       => 'Timezone',
                'is_public'   => true,
            ],
            [
                'key'         => 'date_format',
                'value'       => 'M d, Y',
                'type'        => 'string',
                'group'       => 'display',
                'label'       => 'Date Format',
                'is_public'   => true,
            ],
            [
                'key'         => 'time_format',
                'value'       => 'h:i A',
                'type'        => 'string',
                'group'       => 'display',
                'label'       => 'Time Format',
                'is_public'   => true,
            ],
            [
                'key'         => 'pagination_limit',
                'value'       => '25',
                'type'        => 'integer',
                'group'       => 'display',
                'label'       => 'Records Per Page',
                'is_public'   => false,
            ],
        ];

        foreach ($settings as $data) {
            SystemSetting::firstOrCreate(['key' => $data['key']], $data);
        }
    }
}
